import argparse
import hashlib
import json

from functools import partial

from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor

from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen

from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue

class RePoEComparison:
    """Compare a saved analysis with a pinned RePoE snapshot without changing statuses."""

    ROOT = Path(__file__).resolve().parents[3]

    @staticmethod
    def read_json(path):
        """Read local UTF-8 JSON."""

        return json.loads(path.read_text(encoding = 'utf-8'))

    @staticmethod
    def verified_bytes(path, expected):
        """Verify SHA-256 before using a catalogue or registry."""

        raw = path.read_bytes()

        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f'Hash mismatch: {path}')

        return raw

    @staticmethod
    def fetch_snapshot(lock, output):
        """Download only explicitly listed public files; never read original logs."""

        if output.exists():
            raise FileExistsError('The snapshot directory already exists')

        output.parent.mkdir(parents = True, exist_ok = True)

        with TemporaryDirectory(prefix = '.repoe-', dir = output.parent) as temporary:
            target = Path(temporary) / 'snapshot'
            target.mkdir()


            with ThreadPoolExecutor(max_workers = 4) as pool:
                list(pool.map(partial(RePoEComparison._fetch_entry, target), lock['files']))

            (target / 'snapshot-lock.json').write_text(
                json.dumps(lock, ensure_ascii = False, sort_keys = True, indent = 2) + '\n', encoding = 'utf-8')
            target.rename(output)

    @staticmethod
    def load_tables(snapshot, lock):
        """Use only files from the lock, including source-schema validation."""

        tables = {}

        for entry in lock['files']:
            raw = RePoEComparison.verified_bytes(snapshot / entry['path'], entry['sha256'])

            if entry['path'].startswith('data/') and entry['path'].endswith('.json'):
                tables[entry['path'].removeprefix('data/')] = json.loads(raw)

        return tables

    @staticmethod
    def indexes(tables):
        """Separate identifier namespaces and retain all tree variants."""

        idx = {key: defaultdict(list) for key in ('area_id', 'area_name', 'passive_id',
               'base_class', 'item_name', 'skill_id', 'flavour_line', 'audio_line', 'dialogue_text', 'audio_end')}

        for key, row in tables['world_areas.json'].items():
            ref = {'file': 'world_areas.json', 'key': key, **{k: row[k] for k in
                   ('name', 'act', 'area_level', 'is_town', 'has_waypoint')}}
            idx['area_id'][key].append(ref)
            idx['area_name'][row['name']].append(ref)

        for filename, table in sorted(tables.items()):
            if filename.startswith('passive_skill_trees/'):
                for key, row in table['passives'].items():
                    ref = {'file': filename, 'key': key, **{k: row[k] for k in
                           ('id', 'name', 'hash', 'is_keystone', 'is_notable', 'stats') if k in row}}
                    idx['passive_id'][row['id']].append(ref)

        for row in tables['cluster_jewel_notables.json']:
            idx['passive_id'][row['id']].append({'file': 'cluster_jewel_notables.json', **row})

        for jewel, row in tables['cluster_jewels.json'].items():
            for passive in row['passive_skills']:
                idx['passive_id'][passive['id']].append({'file': 'cluster_jewels.json', 'key': jewel, **passive})

        for row in tables['characters.json']:
            idx['base_class'][row['name']].append({'file': 'characters.json', 'name': row['name'],
                                                'integer_id': row['integer_id']})

        for filename in ('base_items.json', 'uniques.json'):
            for key, row in tables[filename].items():
                idx['item_name'][row['name']].append({'file': filename, 'key': key, 'name': row['name']})

        for row in tables['gems_minimal.json']:
            if skill := row.get('active_skill'):
                idx['skill_id'][skill['id']].append({'file': 'gems_minimal.json', 'id': skill['id'],
                                                   'name': skill['display_name']})

        for key, text in tables['flavour.json'].items():
            # Match exact strings only; normalize CRLF to LF without guessing meaning.
            for number, line in enumerate(text.replace('\r\n', '\n').split('\n'), 1):
                if line:
                    idx['flavour_line'][line].append({'file': 'flavour.json', 'key': key, 'text_line': number})

        for key, row in tables['audio.json'].items():
            text = row.get('text') or ''
            parts = text.replace('\r\n', '\n').split('\n')
            ref = {'file': 'audio.json', 'key': key, 'npcs': row.get('npcs') or []}

            if text:
                idx['dialogue_text'][text].append(ref)
                idx['audio_end'][parts[-1]].append({**ref, 'parts': parts})

            for number, line in enumerate(parts, 1):
                if line:
                    idx['audio_line'][line].append({**ref, 'text_line': number,
                                                    'whole_text': len(parts) == 1})

        return idx

    @staticmethod
    def interpret(row, idx):
        """Return verifiable matches, including ambiguity and naming differences."""

        kind, fields = row['type'], row['fields']
        lookup = {
            'area.generate': ('area_id', 'area'), 'area.enter': ('area_name', 'area'),
            'passive.allocation': ('passive_id', 'skill_id'),
            'mastery.allocated': ('passive_id', 'mastery'),
            'screen.level_up': ('base_class', 'class'),
            'ui.virtual_keyboard': ('item_name', 'default_text'),
            'skill.missing_row': ('skill_id', 'skill'),
            'dialogue.named': ('dialogue_text', 'utterance'),
        }

        if row['status'] == 'unknown':
            text = row.get('text', '')
            match = RuleCatalogue.HEADER.fullmatch(text)
            query = (match['message'] if match else text).removeprefix(': ').removesuffix('\r')
            namespace = 'unknown_text'
        elif kind in lookup and row['status'] == 'recognized':
            namespace, field = lookup[kind]
            query = fields[field]
        else:
            return None

        candidates = (idx['flavour_line'].get(query, []) + idx['audio_line'].get(query, [])
                      if namespace == 'unknown_text' else idx[namespace].get(query, []))
        result = {'line_number': row['line_number'], 'type': kind, 'namespace': namespace,
                  'match': 'found' if candidates else 'missing', 'candidates': candidates}

        # Never copy unknown text or player names into comparison results.
        if namespace not in ('unknown_text', 'dialogue_text'):
            result['query'] = query

        if namespace == 'passive_id' and candidates:
            result['log_name'] = fields['name']
            result['name_matches'] = any(c['name'] == fields['name'] for c in candidates)
            result['candidate_names'] = sorted({c['name'] for c in candidates})

        if kind == 'area.generate' and candidates:
            result['log_level'] = int(fields['level'])
            result['default_level_matches'] = int(fields['level']) == candidates[0]['area_level']

        if namespace in ('area_name', 'item_name') and candidates:
            result['match'] = 'unique_name' if len(candidates) == 1 else 'ambiguous_name'

        return result

    @staticmethod
    def compare(directory, idx):
        """Verify the saved registry hash; return counts and line references."""

        manifest = RePoEComparison.read_json(directory / 'manifest.json')
        coverage = json.loads(RePoEComparison.verified_bytes(directory / 'coverage.json', manifest['artifacts_sha256']['coverage.json']))

        if coverage['input_sha256'] != manifest['input']['sha256']:
            raise ValueError('Coverage source does not match the manifest')

        digest = hashlib.sha256()
        counts, statuses = Counter(), Counter()
        matches, blocks = [], []
        max_lines = max((len(r['parts']) for refs in idx['audio_end'].values() for r in refs), default = 1)
        recent = deque(maxlen = max_lines)

        with (directory / 'lines.jsonl').open('rb') as ledger:
            for number, raw in enumerate(ledger, 1):
                digest.update(raw)
                row = json.loads(raw)

                if row['line_number'] != number:
                    raise ValueError('Invalid registry line order')

                statuses[row['status']] += 1
                body = row.get('text', '')
                header = RuleCatalogue.HEADER.fullmatch(body)
                body = row['fields']['utterance'] if row['type'] == 'dialogue.named' else (
                    header['message'] if header else body).removeprefix(': ').removesuffix('\r')
                recent.append((row, body))

                for candidate in idx['audio_end'].get(body, []):
                    size = len(candidate['parts'])

                    if size < 2 or len(recent) < size:
                        continue

                    span = list(recent)[-size:]
                    first = span[0][0]

                    if (all(r['status'] != 'error' for r, _ in span)
                            and first['type'] == 'dialogue.named'
                            and first['fields']['speaker'] in {n['name'] for n in candidate['npcs']}
                            and [text for _, text in span] == candidate['parts']):
                        blocks.append({'key': candidate['key'], 'first_line': first['line_number'],
                                       'last_line': number, 'unknown_lines': [r['line_number'] for r, _ in span
                                                                             if r['status'] == 'unknown']})

                match = RePoEComparison.interpret(row, idx)

                if match:
                    prefix = match['namespace']
                    counts[prefix + '.total'] += 1
                    counts[prefix + '.' + match['match']] += 1

                    if match.get('name_matches') is False:
                        counts[prefix + '.name_conflict'] += 1

                    if match.get('default_level_matches') is False:
                        counts[prefix + '.level_diff'] += 1

                    matches.append(match)

        if digest.hexdigest() != manifest['artifacts_sha256']['lines.jsonl']:
            raise ValueError('Registry hash does not match the manifest')

        if (sum(statuses.values()) != coverage['total_lines'] or any(
                statuses[status] != coverage[status + '_lines'] for status in ('recognized', 'unknown', 'error'))):
            raise ValueError('Line count does not match coverage')

        return {'input_sha256': coverage['input_sha256'], 'rules_version': coverage['rules_version'],
                'total_lines': coverage['total_lines'], 'unknown_lines': coverage['unknown_lines'],
                'error_lines': coverage['error_lines'], 'counts': dict(sorted(counts.items())),
                'audio_blocks': blocks, 'matches': matches}

    @staticmethod
    def main():
        """Download a snapshot or perform an entirely local comparison."""

        parser = argparse.ArgumentParser(description = __doc__)
        parser.add_argument('--lock', type = Path, default = RePoEComparison.ROOT / 'docs/repoe-snapshot.json', help = 'snapshot manifest')
        parser.add_argument('--snapshot', type = Path, required = True, help = 'catalogue directory')
        parser.add_argument('--fetch', action = 'store_true', help = 'only download the pinned snapshot into a new directory')
        parser.add_argument('--result', type = Path, action = 'append', help = 'saved analysis; may be repeated')
        parser.add_argument('--output', type = Path, help = 'new comparison-result JSON file')
        args = parser.parse_args()
        lock = RePoEComparison.read_json(args.lock)

        if args.fetch:
            if args.result or args.output:
                parser.error('--fetch cannot be combined with --result or --output')

            RePoEComparison.fetch_snapshot(lock, args.snapshot)
            print(f'Snapshot saved: {args.snapshot}')
            return

        if not args.result or not args.output:
            parser.error('Comparison requires --result and --output')

        if args.output.exists():
            raise FileExistsError('The comparison result already exists')

        idx = RePoEComparison.indexes(RePoEComparison.load_tables(args.snapshot, lock))
        results = [RePoEComparison.compare(directory, idx) for directory in args.result]
        output = {'comparison_version': '1', 'comparison_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'snapshot_lock_sha256': hashlib.sha256(args.lock.read_bytes()).hexdigest(),
                  'data_commit': lock['data_commit'], 'game_version': lock['game_version'], 'results': results}
        args.output.parent.mkdir(parents = True, exist_ok = True)

        with args.output.open('x', encoding = 'utf-8') as target:
            json.dump(output, target, ensure_ascii = False, sort_keys = True, indent = 2)
            target.write('\n')

        for result in results:
            print(result['input_sha256'], json.dumps(result['counts'], ensure_ascii = False, sort_keys = True))

    @staticmethod
    def _fetch_entry(target, entry):
        # The URL and path come from the project's locally validated lock file.
        with urlopen(entry['url'], timeout = 120) as response:
            raw = response.read()

        if hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError(f"Download hash mismatch: {entry['path']}")

        path = target / entry['path']

        if not path.resolve().is_relative_to(target.resolve()):
            raise ValueError('The catalogue path escapes the snapshot directory')

        path.parent.mkdir(parents = True, exist_ok = True)
        path.write_bytes(raw)
