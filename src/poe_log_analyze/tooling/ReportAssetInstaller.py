"""Prepare local report resources from pinned public sources."""

import hashlib
import json

from concurrent.futures import ThreadPoolExecutor

from pathlib import Path
from urllib.request import urlopen


class ReportAssetInstaller:
    """Download Bootstrap and game icons during development, not when opening reports."""

    ROOT = Path(__file__).resolve().parents[3]
    BOOTSTRAP = "5.3.8"

    @staticmethod
    def download(item):
        path, url = item

        if not path.is_file():
            with urlopen(url, timeout = 30) as response:
                data = response.read()

            if path.suffix == '.png' and not data.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError(f'The response is not a PNG: {url}')

            path.parent.mkdir(parents = True, exist_ok = True)
            path.write_bytes(data)

        return {"path": path.relative_to(ReportAssetInstaller.ROOT).as_posix(),
                "url": url, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    @staticmethod
    def main():
        root = ReportAssetInstaller.ROOT
        lock = json.loads((root/'docs/repoe-snapshot.json').read_text())
        folder = root/'build/repoe-research/snapshot/data'

        for name in ('world_areas.json', 'base_items.json', 'uniques.json'):
            expected = next(item['sha256'] for item in lock['files'] if item['path'] == 'data/'+name)
            assert hashlib.sha256((folder/name).read_bytes()).hexdigest() == expected, name

        worlds = json.loads((folder/'world_areas.json').read_text())
        bases = json.loads((folder/'base_items.json').read_text())
        uniques = json.loads((folder/'uniques.json').read_text())
        unique_icons = {v['name']: v['visual_identity']['dds_file'] for v in uniques.values()
                        if v.get('item_class') == 'Map' and v.get('visual_identity') and v['visual_identity'].get('dds_file')}
        map_items = {v['name']: v for key,v in sorted(bases.items(), key = lambda pair: ('MapWorlds' in pair[0], pair[0]))
                     if v['item_class'] == 'Map'}
        areas, icons = {}, {}

        for key, value in worlds.items():
            item = bases.get('Metadata/Items/Maps/'+key) or map_items.get(value['name']+' Map', {})
            # Side areas also have the map tag; require an associated map item.
            kind = 'Карта' if item.get('item_class') == 'Map' or value['name'] in unique_icons else 'Область'

            if value['is_town']:
                kind = 'Город'
            elif key.startswith('Hideout'):
                kind = 'Убежище'
            elif key.startswith(('MapWorldsPrimordialBoss', 'MapWorldsMemoryBoss', 'MapWorldsElderArena', 'MapWorldsShapersRealm')):
                kind = 'Арена'

            art = unique_icons.get(value['name']) or (item.get('visual_identity') or {}).get('dds_file')
            icon = ''

            if kind == 'Карта' and art:
                icon = 'images/maps/'+hashlib.sha256(art.encode()).hexdigest()[:16]+'.png'
                icons[icon] = 'https://web.poecdn.com/image/'+art.removesuffix('.dds')+'.png'

            areas[key] = {'name': value['name'], 'kind': kind, 'icon': icon}

        # Older map generations reuse the current item icon with the same name.
        by_name = {item['name']:item['icon'] for key,item in areas.items() if key.startswith('MapWorlds') and item['icon']}

        for area in areas.values():
            if area['kind']=='Карта' and not area['icon']:
                area['icon'] = by_name.get(area['name'],'')

        downloads = [(root/'site/static'/path, url) for path,url in sorted(icons.items())]
        prefix = 'https://cdn.jsdelivr.net/npm/bootstrap@'+ReportAssetInstaller.BOOTSTRAP
        downloads += [(root/'site/static/vendor/bootstrap.min.css', prefix+'/dist/css/bootstrap.min.css'),
                      (root/'site/static/vendor/bootstrap.bundle.min.js', prefix+'/dist/js/bootstrap.bundle.min.js'),
                      (root/'site/static/vendor/bootstrap-LICENSE.txt', prefix+'/LICENSE')]
        results, failed = [], []

        with ThreadPoolExecutor(max_workers = 6) as pool:
            futures = [(item, pool.submit(ReportAssetInstaller.download,item)) for item in downloads]

            for item, future in futures:
                try:
                    results.append(future.result())
                except Exception as error:
                    failed.append({'url':item[1],'error':str(error)})

        available = {item['path'].removeprefix('site/static/') for item in results}

        for area in areas.values():
            if area['icon'] not in available:area['icon'] = ''

        (root/'site/data').mkdir(exist_ok = True)
        (root/'site/data/areas.json').write_text(json.dumps({'version':'1','repoe_commit':lock['data_commit'],'areas':areas},ensure_ascii = False,sort_keys = True,indent = 2)+'\n')
        (root/'docs/report-assets.json').write_text(json.dumps({'bootstrap':ReportAssetInstaller.BOOTSTRAP,'repoe_commit':lock['data_commit'],'files':results,'unavailable':failed},ensure_ascii = False,indent = 2)+'\n')
        print(json.dumps({'downloaded':len(results),'unavailable':len(failed),'area_icons':sum(bool(a['icon']) for a in areas.values())}))

        if any('bootstrap' in item['url'] for item in failed):
            raise RuntimeError('Bootstrap is not installed')
