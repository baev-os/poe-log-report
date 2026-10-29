# Recognition rules

Family and message reference for report generation.

### Areas, characters and game operations

#### `area`

Generation specifies level, the quoted area identifier and seed. Entry matches exactly ": You have entered ….". Tile/Doodad hashes are decimal numbers. Two diagnostic phrases are matched literally. Generation alone does not prove a map visit.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `area.tile_hash` | 4 | `value` | Area tile checksum |
| `area.doodad_hash` | 5 | `value` | Area decoration checksum |
| `area.generate` | 6 | `level`, `area`, `seed` | Area generation with level and seed |
| `area.enter` | 7 | `area` | Area entry |
| `area.unconnected_depth` | 56 | — | Unreachable area depth |
| `area.activation_range_late` | 172 | — | Activation range set too late |

#### `instance`

Login server details and decimal Client-Safe Instance ID are separate messages. Analytics establishes their relationship to a visit.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `instance.details` | 2 | — | Game instance details |
| `instance.id` | 3 | `instance_id` | Client-safe instance identifier |

#### `loading`

An area name in parentheses and Duration in seconds, using NUMBER syntax. Loading time is not a visit duration.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `loading.duration` | 14 | `area`, `seconds` | Loading duration |

#### `hideout`

Exact Spawning discoverable Hideout form, with a Hideout… identifier made of letters, digits and underscores.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `hideout.discoverable` | 135 | `hideout` | Discoverable hideout spawned |

#### `passive`

Operation allocated/unallocated, skill identifier (letters, digits, underscore and apostrophe) and nonempty name. Parsing does not validate the identifier against an external catalogue.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `passive.allocation` | 39 | `operation`, `skill_id`, `name` | Passive skill allocated or unallocated |

#### `mastery`

Numeric effect ID, mastery identifier and nonempty name in the exact Successfully allocated mastery effect id form.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `mastery.allocated` | 137 | `effect_id`, `mastery`, `name` | Mastery effect allocated |

#### `jewel`

ALTERNATE TREE JEWEL with decimal version, seed and keystone selection. Values are retained without interpreting the tree.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `jewel.alternate_tree` | 9 | `version`, `seed`, `keystone` | Alternate jewel tree |

#### `currency`

Literal CurrencyApplicationForesightResult recieved marker. The original typo is preserved. The marker does not establish the result of currency use.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `currency.foresight` | 118 | — | Foresight currency result marker |

#### `labyrinth`

Literal InstanceClientLabyrinthCraftResultOptionsList recieved marker, preserving the original typo.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `labyrinth.craft_options` | 119 | — | Labyrinth crafting options |

#### `settlers`

GoldRespec with integer PassivesAllocated and GoldCost and exact vertical separators. Numbers remain strings.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `settlers.gold_respec` | 240 | `allocated`, `gold` | Gold cost of passive respec |

#### `trade`

Exact local player brought an item for … gold phrase. It does not determine the direction of item or money transfer.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `trade.gold` | 40 | `gold` | Gold message for an acquired item |

#### `etrade`

Service requests and responses: API type, request_id, error and latency in ms. A recognized response does not prove a successful player trade.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `etrade.request` | 37 | `api_type`, `request_id` | Trade service request |
| `etrade.response` | 38 | `request_id`, `error`, `milliseconds` | Trade service response |

#### `stash`

Two exact phrases for reordering tabs and subtabs to match stash data.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `stash.reorder` | 136 | — | Stash tabs reordered |
| `stash.reorder_subtabs` | 174 | — | Stash subtabs reordered |

#### `tutorial`

Exact request to complete tutorials due to a client setting. The parser performs no game operation.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `tutorial.complete_request` | 160 | — | Request to complete all tutorials |

### Screen notifications

#### `screen`

Every rule requires the ": " prefix after the client header and a full format match. Character names exclude spaces and colons; names and classes are not validated against a registry. Numeric values remain strings. Point types, item actions, resistance and movement rewards, Kitava penalties and crafting notices accept only the alternatives in their patterns. apply_failed uses the finite APPLY_FAILURES list; use_failed has two explicit reasons. Trade accepted/cancelled and the expired hideout trade warning do not identify items, price or partner. Character messages may refer to others. Death/kill counters, played time and character age are displayed totals, not new events to add together. Duration variants preserve singular/plural forms. Remaining monsters has a separate singular form; comma-separated counts use groups of three digits. AFK ON/OFF is exact; the quoted reply may be empty. Bestiary, Hiveblood, divination card markup and Expedition artifact types accept only observed forms. screen.phrase.* covers the finite SCREEN_PHRASES list and Become the nightmare. The trailing space in "Overpower, overrun, overcome. " is required. No speaker, cause or action is inferred from a phrase. Other notifications are individual exact patterns, not a catch-all for any prefixed text. Optional chest_locked.key_required is null when the Treasure Key phrase is absent; otherwise its original delimiters are retained. Tree-roots notices have an exact three-line continuation sequence; screen phrases match a finite list. Supporter inscriptions are not inferred from a generic screen prefix.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `screen.point_received` | 95 | `article`, `point` | One point received |
| `screen.points_received` | 96 | `count`, `point` | Multiple points received |
| `screen.items_identified` | 97 | `count`, `label` | Items identified |
| `screen.chest_locked` | 98 | `key_required` | Chest locked |
| `screen.trade` | 99 | `state` | Player trade result |
| `screen.cursor_item_destroyed` | 100 | — | Item on cursor destroyed |
| `screen.apply_failed` | 101 | `reason` | Item application failed |
| `screen.stash_full` | 102 | `affinity` | Stash full |
| `screen.slain` | 103 | `character` | Character death message |
| `screen.suicide` | 264 | `character` | Character death from self-damage |
| `screen.nameless_seer` | 265 | — | Nameless Seer appeared nearby |
| `screen.reflecting_mist` | 266 | — | Reflecting Mist appeared nearby |
| `screen.level_up` | 104 | `character`, `class`, `level` | Character level increased |
| `screen.afk_on` | 105 | `reply` | AFK mode enabled |
| `screen.afk_off` | 106 | — | AFK mode disabled |
| `screen.area_presence` | 107 | `character`, `action` | Character entered or left an area |
| `screen.death_count` | 108 | `count` | Displayed death count |
| `screen.kill_count` | 109 | `count` | Displayed kill count |
| `screen.played_time` | 110 | `hours`, `minutes`, `seconds` | Displayed character playtime |
| `screen.character_age` | 111 | `days`, `hours`, `minutes`, `seconds` | Displayed character age |
| `screen.area_unreachable` | 138 | — | Area unreachable |
| `screen.portals_disabled` | 139 | — | Portals disabled |
| `screen.bestiary_added` | 140 | — | Beast added to the Bestiary |
| `screen.hiveblood_warning` | 141 | — | Hiveblood warning |
| `screen.phrase.fear_not_elements` | 142 | — | On-screen phrase: Fear not the elements |
| `screen.phrase.eye_of_storm` | 143 | — | On-screen phrase: Open the eye of the storm |
| `screen.phrase.world_to_ice` | 144 | — | On-screen phrase: Turn your world to ice |
| `screen.phrase.none_shall_stop` | 145 | — | On-screen phrase: None shall stop you |
| `screen.phrase.courage` | 146 | — | On-screen phrase: Courage stands tall |
| `screen.phrase.fog_of_war` | 147 | — | On-screen phrase: Shroud your path in the fog of war |
| `screen.phrase.death_wait` | 148 | — | On-screen phrase: Death does not wait |
| `screen.phrase.past_serves_present` | 149 | — | On-screen phrase: The past shall serve the present |
| `screen.phrase.restore_lost` | 150 | — | On-screen phrase: Restore that which was lost |
| `screen.phrase.hit_once` | 151 | — | On-screen phrase: Hit hard. Hit once |
| `screen.phrase.pain_exquisite` | 152 | — | On-screen phrase: Pain is exquisite |
| `screen.phrase.overpower` | 153 | — | On-screen phrase: Overpower, overrun, overcome |
| `screen.phrase.rage` | 154 | — | On-screen phrase about rage |
| `screen.phrase.shadows` | 155 | — | On-screen phrase about shadows |
| `screen.quest_points` | 177 | `count` | Quest reward points |
| `screen.quest_contribution` | 178 | `count`, `quest` | Quest completion contribution |
| `screen.ascendancy_points` | 179 | `total`, `allocated` | Ascendancy points |
| `screen.resistance_reward` | 180 | `percent` | Resistance reward |
| `screen.kitava_affliction` | 181 | `kind`, `total`, `percent` | Kitava affliction |
| `screen.betrayal_busy` | 182 | — | Betrayal system busy |
| `screen.hideout_trade_expired` | 183 | — | Trading in an expired hideout instance |
| `screen.locked` | 184 | — | Action or object locked |
| `screen.bug_submitted` | 185 | — | Bug report submitted |
| `screen.phrase.become_nightmare` | 186 | — | On-screen phrase: Become the nightmare |
| `screen.character_info` | 187 | `character`, `level`, `class`, `league`, `area` | Character information |
| `screen.played_time_days` | 209 | `days`, `hours`, `minutes`, `seconds` | Playtime including days |
| `screen.played_time_minutes` | 210 | `minutes`, `seconds` | Playtime in minutes and seconds |
| `screen.character_age_hours` | 211 | `hours`, `minutes`, `seconds` | Character age in hours |
| `screen.use_failed` | 212 | `reason` | Object use failed |
| `screen.passive_points` | 213 | `total`, `allocated` | Passive point totals |
| `screen.level_points` | 214 | `count` | Points from levels |
| `screen.monsters_remaining` | 215 | `single`, `count` | Remaining monster count |
| `screen.bug_reference` | 216 | `reference` | Bug report reference number |
| `screen.card_drawn` | 217 | `card` | Card drawn |
| `screen.expedition_added` | 218 | `count`, `artifact` | Expedition artifacts added |
| `screen.movement_reward` | 219 | `percent` | Movement speed reward |
| `screen.favoured_resources_busy` | 220 | — | Favoured resources busy |
| `screen.hideout_quest_required` | 221 | — | Quest required for hideout |
| `screen.recipe_already_unlocked` | 222 | — | Recipe already unlocked |
| `screen.passage_item_required` | 223 | — | Item required for passage |
| `screen.join_instances_failed` | 224 | — | Failed to join instances |
| `screen.corrupted_target` | 225 | — | Cannot modify a corrupted target |
| `screen.door_locked` | 226 | — | Door locked |
| `screen.foreign_bench` | 227 | — | Another player's crafting bench |
| `screen.crafting_no_target` | 228 | — | No crafting target selected |
| `screen.lantern_required` | 229 | — | Lantern required |
| `screen.achievement_server_failed` | 230 | — | Achievement server error |
| `screen.pvp_list_timeout` | 231 | — | PvP list request timed out |
| `screen.recombinator_cost` | 232 | — | Recombinator cost |
| `screen.activation_cancelled` | 233 | — | Activation cancelled |
| `screen.golden_key_required` | 234 | — | Golden key required |
| `screen.item_no_room` | 235 | — | Not enough room for item |
| `screen.contract_low_level` | 236 | — | Level too low for contract |
| `screen.join_maintenance` | 237 | — | Cannot join during maintenance |
| `screen.join_disconnected` | 238 | — | Joining interrupted by disconnection |
| `screen.mission_client_required` | 239 | — | Mission client must be present |
| `screen.phrase.goddess_watching` | 248 | — | Screen line about the watching Goddess |
| `screen.phrase.heart_desire` | 249 | — | Screen line about the heart’s desire |
| `screen.phrase.water_motion` | 250 | — | Screen line about still water |
| `screen.phrase.wah_get_beh` | 251 | — | Screen line Wah get beh |
| `screen.phrase.thrill_void` | 252 | — | Screen line about the void |
| `screen.phrase.unmake` | 253 | — | Screen threat of destruction |
| `screen.phrase.sink_stone` | 254 | — | Screen line about sinking |
| `screen.phrase.conqueror` | 255 | — | Screen line about conqueror and conquered |
| `screen.phrase.darkness_looms` | 256 | — | Screen notice of looming darkness |
| `screen.phrase.room_quiet` | 257 | — | Screen notice of a quiet room |
| `screen.phrase.drought` | 258 | — | Screen notice of continuing drought |
| `screen.phrase.waters_flow` | 259 | — | Screen line about flowing water |
| `screen.phrase.atmosphere_dissipates` | 260 | — | Screen notice of a dissipating oppressive atmosphere |
| `screen.microtransaction_converted` | 261 | — | Item converted to an account-bound microtransaction |
| `screen.tree_roots_blocked` | 262 | — | Tree roots block the path |

### Chat and named dialogue

#### `reliquary`

A custom chest message requires generation of a RELIQUARY_AREAS ID, a matching scene, entry and completed loading in the same client context. One INFO message is accepted per visit. System rules retain priority, except thrill_void and conqueror in this context. Consecutive unframed text lines belong to the same message until a new header, blank or invalid line. Area changes, log opening, disconnects, invalid records, client changes or tick regression reset the context. Item identity and pickup are not inferred. A temporary (null) scene is allowed before entry. Closing the game or connecting to another instance also resets the context.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `reliquary.message` | 267 | `message` | Chest message in a confirmed Reliquary context |

#### `chat`

Channel messages start with % or #; whispers with @To or @From. An optional guild tag, character name excluding spaces/colons/angle brackets and possibly empty text follow. Markers, direction and text are preserved literally. Text is never executed, and a trade offer does not prove a completed trade. Conversations are displayed on their dedicated local report page. Unprefixed local chat requires a character name previously confirmed by a character notification or marked chat earlier in the same file, including previous log-opening sessions. One optional leading NUL is preserved as a marker; other controls are rejected. Known dialogue signatures retain priority.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `chat.channel` | 156 | `channel`, `guild`, `character`, `message` | Public or party chat message |
| `chat.whisper` | 157 | `direction`, `guild`, `character`, `message` | Incoming or outgoing private message |
| `chat.local` | 246 | `guild`, `character`, `marker`, `message` | Local chat from a confirmed character or an INFO message with a guild tag |

#### `dialogue`

Only the finite SPEAKERS catalogue is accepted. A final CR can introduce a paragraph only when followed immediately by a CR-only separator and one nonempty line without controls or an initial timestamp. Headers and unframed text without the separator are not consumed. A signature alone does not establish the speaker’s role.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `dialogue.named` | 112 | `speaker`, `utterance` | Game dialogue with a known speaker label |

### Actions and GEAL

#### `action`

Exact triggered/instant/update/animation/channelling errors, preserving actionwas. ContactAttack requires a Metadata/… path. Continuation fields are listed separately. A runtime action ID is not assumed to be a game skill ID.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `action.trigger_failed` | 10 | — | Server action trigger failed |
| `action.execute_failed` | 11 | — | Client action execution failed |
| `action.detach_finished` | 42 | `action_type_id` | Action detach completed |
| `action.update_missing` | 114 | — | Action to update not found |
| `action.instant_failed` | 188 | — | Instant action failed |
| `action.animation_missing` | 189 | — | Action animation missing |
| `action.channel_mismatch` | 190 | — | Action channel mismatch |
| `action.contact_bone_invalid` | 191 | `path` | Invalid contact bone |

#### `geal`

Object errors contain a hexadecimal object_id, signed integer x/y coordinates, a Metadata/… path and one GEAL_REASONS value. Missing animation events and a Metadata/….ao path with a specific empty-result reason have separate rules.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `geal.error` | 133 | `object_id`, `x`, `y`, `path`, `reason` | GEAL execution error |
| `geal.animation_event_missing` | 200 | — | GEAL animation event missing |
| `geal.path_error` | 201 | `path`, `reason` | GEAL path error |

### Engine, startup and internal subsystems

#### `engine`

Versions have 2–4 numeric components; revision is an integer. Directories are Settings/Current/Cache/Download; cache names may include underscores. Found/deleted pipeline cache paths accept .foz, .bin, .toc, /TOUCH or /index, NUMBER size and B/KB/MB/GB units. Lifecycle stages are Init, Ready and Reset static. Windows Version/OS text and Build are recorded as client output; they do not contradict the confirmed Ubuntu/Steam origin of the logs.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `engine.pipeline_cache` | 19 | `path`, `size`, `unit` | Engine pipeline cache |
| `engine.build_revision` | 20 | `revision` | Client build revision |
| `engine.version` | 21 | `version` | Engine version |
| `engine.directory` | 22 | `kind`, `path` | Engine directory |
| `engine.wipe_cache` | 23 | `cache`, `path` | Engine cache cleared |
| `engine.os` | 24 | `kind`, `version`, `build` | Operating system information reported by the client |
| `engine.lifecycle` | 25 | `stage` | Engine lifecycle stage |
| `engine.deleted_pipeline` | 134 | `path`, `size`, `unit` | Pipeline cache deleted |
| `engine.old_version` | 198 | `version` | Old engine version detected |

#### `startup`

Start and duration of Registration/Game/Device/Tencent/Loading/DebugGUI stages. Duration is NUMBER in seconds.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `startup.stage_start` | 47 | `stage` | Startup stage started |
| `startup.stage_duration` | 48 | `stage`, `seconds` | Startup stage duration |

#### `game`

Exact Closing game gracefully phrase. Log opening alone does not establish a game session boundary.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `game.closing` | 117 | — | Game closing |

#### `setting`

Only subsystem/setting pairs in BOOLEAN_SETTINGS and ON/OFF state are accepted. A setting from one subsystem cannot be transferred to another. The observed MAT: Ingore Temp typo is preserved; an unverified corrected spelling is not accepted.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `setting.engine` | 57 | `subsystem`, `setting`, `state` | Engine boolean setting |
| `setting.graph` | 58 | `subsystem`, `setting`, `state` | Graph boolean setting |
| `setting.job` | 59 | `subsystem`, `setting`, `state` | Job boolean setting |
| `setting.mat` | 60 | `subsystem`, `setting`, `state` | Material boolean setting |
| `setting.mesh` | 61 | `subsystem`, `setting`, `state` | Mesh boolean setting |
| `setting.particle` | 62 | `subsystem`, `setting`, `state` | Particle boolean setting |
| `setting.render` | 63 | `subsystem`, `setting`, `state` | Render boolean setting |
| `setting.resource` | 64 | `subsystem`, `setting`, `state` | Resource boolean setting |
| `setting.shader` | 65 | `subsystem`, `setting`, `state` | Shader boolean setting |
| `setting.sound` | 66 | `subsystem`, `setting`, `state` | Sound boolean setting |
| `setting.storage` | 67 | `subsystem`, `setting`, `state` | Storage boolean setting |
| `setting.texture` | 68 | `subsystem`, `setting`, `state` | Texture boolean setting |
| `setting.trails` | 69 | `subsystem`, `setting`, `state` | Trails boolean setting |
| `setting.video` | 70 | `subsystem`, `setting`, `state` | Video boolean setting |

#### `job`

HIGH/MEDIUM/LOW/IDLE priorities and count; exact Start, Exception Callback: SET and true/false priority boost.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `job.priority_count` | 71 | `priority`, `count` | Background job priority count |
| `job.start` | 72 | — | Background job startup |
| `job.exception_callback` | 73 | — | Background job exception handler registration |
| `job.priority_boost` | 74 | `enabled` | Job priority boost |

#### `storage`

Mapping bucket count and exact bundle cache initialization.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `storage.bucket_count` | 75 | `count` | Storage bucket count |
| `storage.init_cache` | 76 | — | Bundle cache initialization |

#### `runtime`

Dynamic Bucket count for MESH/MAT/GRAPH with an integer value.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `runtime.bucket_count` | 77 | `subsystem`, `count` | Runtime bucket count |

#### `bundle`

BundlesN/….bin index path, entries/slots/directories counts, NUMBER size and B/KB/MB/GB units.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `bundle.index` | 78 | `path` | Resource bundle index |
| `bundle.contents` | 79 | `count`, `kind`, `size`, `unit` | Resource bundle contents |

#### `memory`

Used, OsUsed and Total with a separate B/KB/MB/GB unit for each NUMBER. Units are not converted.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `memory.usage` | 88 | `used`, `used_unit`, `os_used`, `os_unit`, `total`, `total_unit` | Memory usage |

#### `precalc`

Only table names in PRECALC_TABLES after Precalc are accepted.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `precalc.table` | 115 | `table` | Table precalculation |

#### `entity2`

Regather Pass Types or Object Types.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `entity2.regather` | 199 | `kind` | Entity2 data regather |

#### `lmdb`

Environment path and exact Access denied error. After removing LF/CRLF, exactly one additional CR may remain; it is saved as trailing_cr, otherwise an empty string. No global strip is applied. raw_base64 retains the entire original delimiter.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `lmdb.access_denied` | 116 | `path`, `trailing_cr` | LMDB access denied |

### Graphics, devices and window

#### `render`

Device start with null backend, Vulkan or DirectX11; 2–4 component driver versions; GPU scheduling Enabled/Disabled. Exact startup failure, DirectX11 fallback, Blit overflow and enumerated restart stages. A diagnostic line does not prove rendering succeeded.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `render.start_device` | 80 | `backend` | Graphics device startup |
| `render.driver_version` | 81 | `version` | Graphics driver version |
| `render.gpu_scheduling` | 82 | `state` | GPU scheduling |
| `render.blit_overflow` | 170 | — | Blit buffer overflow |
| `render.device_failed` | 206 | — | Graphics device failure |
| `render.fallback_d3d11` | 207 | — | Fallback to Direct3D 11 |
| `render.lifecycle` | 208 | `operation` | Render system lifecycle stage |

#### `adapter`

Adapter name, integer Selected/Max feature levels and a DISPLAY device path with a numeric suffix.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `adapter.enumerated` | 120 | `adapter` | Graphics adapter found |
| `adapter.device` | 121 | `adapter`, `selected`, `maximum` | Selected adapter device |
| `adapter.output` | 122 | `adapter`, `output` | Graphics adapter output |

#### `d3d11`

Buffer count, two-component runtime/feature versions, enumerated YES/NO driver capabilities, Intel/NVidia vendor and fullscreen 0/1.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `d3d11.buffer_count` | 192 | `count` | Direct3D 11 buffer count |
| `d3d11.runtime_version` | 193 | `version` | Direct3D 11 runtime version |
| `d3d11.feature_level` | 194 | `version` | Direct3D 11 feature level |
| `d3d11.driver_capability` | 195 | `capability`, `state` | Graphics driver capability |
| `d3d11.vendor` | 196 | `vendor` | Graphics adapter vendor |
| `d3d11.swapchain_fullscreen` | 197 | `state` | Swap chain fullscreen mode |

#### `vulkan`

Supported/Requesting instance/device VK_… extensions; Fifo/Immediate/Mailbox/FifoRelaxed present modes and a separate hexadecimal invalid value. SwapChain dimensions, Min Image Count, heaps, Graphics/Transfer queues and GPU data are retained. Properties/flags require exact brace and separator syntax; combinations are not interpreted. LUID is hexadecimal and device text nonempty. Lifecycle stages and unsupported transfer queue use the exact finite alternatives. Extensions are validated syntactically without an external registry. The word invalid does not imply a parser error.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `vulkan.extension` | 26 | `action`, `scope`, `extension` | Supported or requested Vulkan extension |
| `vulkan.present_mode` | 27 | `kind`, `mode` | Image presentation mode |
| `vulkan.invalid_present_mode` | 28 | `value` | Invalid presentation mode |
| `vulkan.swapchain` | 29 | `operation`, `width`, `height` | Swap chain creation or parameters |
| `vulkan.min_images` | 30 | `count` | Minimum image count |
| `vulkan.memory_type` | 31 | `heap_index`, `properties` | Vulkan memory type |
| `vulkan.memory_heap` | 32 | `size`, `unit`, `flags` | Vulkan memory heap |
| `vulkan.queue` | 33 | `family`, `count`, `flags` | Vulkan queue |
| `vulkan.selected_queue` | 34 | `kind`, `family`, `index` | Selected graphics or transfer queue |
| `vulkan.gpu_type` | 35 | `kind`, `vendor` | Vulkan GPU type |
| `vulkan.lifecycle` | 36 | `operation` | Graphics resource reinitialization |
| `vulkan.physical_device` | 127 | `luid`, `device` | Physical graphics device found |
| `vulkan.transfer_unsupported` | 245 | — | Separate transfer queue unsupported |

#### `shader`

Cache identifier, PSO Enabled/Disabled and the exact missing ShaderCacheVulkan.packed/index.dat error.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `shader.load_cache` | 83 | `cache` | Shader cache loading |
| `shader.pso_cache` | 84 | `state` | PSO pipeline cache |
| `shader.cache_missing` | 241 | `path` | Shader cache missing |

#### `dxc`

Exact dxcompiler.dll load message; the library name is retained.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `dxc.loaded` | 89 | `library` | DXC shader compiler loaded |

#### `streamline`

Initialization and NUMBER duration; DLSS/Reflex/PCL component and NGX versions (2–4 components); NIS/FSR/XeSS/PSSR proxies. Enabled true/false for the supported components and Reflex Low Latency/Flash Indicator ON/OFF. Shutdown Start/complete and decimal duration without exponent.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `streamline.init` | 49 | `stage` | Streamline initialization |
| `streamline.init_duration` | 50 | `seconds` | Streamline initialization duration |
| `streamline.version` | 51 | `component`, `version`, `ngx_version` | Streamline component version |
| `streamline.proxy` | 52 | `component` | Streamline proxy component |
| `streamline.enabled` | 53 | `component`, `enabled` | Streamline component enabled state |
| `streamline.reflex` | 54 | `setting`, `state` | NVIDIA Reflex setting |
| `streamline.shutdown` | 242 | `stage` | Streamline shutdown |
| `streamline.shutdown_duration` | 243 | `seconds` | Streamline shutdown duration |

#### `window`

Lost/Gained focus, TriggerDeviceCreate/TriggerDeviceReset/TriggerDeviceDestroyed and NUMBER DPI scale. Focus loss does not prove inactivity.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `window.focus` | 1 | `state` | Window focus gained or lost |
| `window.device` | 46 | `operation` | Window graphics device event |
| `window.dpi_scale` | 86 | `scale` | Window DPI scale |

### Scenes, resources and graphs

#### `scene`

Static Walkability Texture and Height Map Texture with integer dimensions. Set Source contains nonempty bracketed text; (null) and (unknown) are preserved literally.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `scene.walkability` | 8 | `width`, `height` | Scene walkability |
| `scene.source` | 12 | `source` | Scene data source |
| `scene.height_map` | 13 | `width`, `height` | Scene height map |

#### `asset`

Art/….ast path and bone name with letters, digits, underscores and optional nonempty segments separated by vertical bars; exact has no vertex influences ending.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `asset.bone_no_influences` | 41 | `asset`, `bone` | Asset bone has no vertex influences |

#### `effect`

Numeric missing node type ID, or a node name and quoted .fxgraph path.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `effect.missing_node_type` | 43 | `node_id` | Effect node type missing |
| `effect.missing_node` | 44 | `node`, `graph` | Effect node missing |

#### `mat`

Table size, combination count and parameter count with exact double spaces. Missing table uses a separate literal phrase.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `mat.table` | 85 | `size`, `combinations`, `parameters` | Material subsystem table |
| `mat.table_missing` | 173 | — | Material table missing |

#### `graph`

Deadlock with timeout in ms and no running graph or running graph nodes: Present/RecordUI state.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `graph.deadlock` | 202 | `timeout_ms`, `state` | Graph deadlock detected |

#### `pathfinding`

CalculateShortestPathToRoot and an integer number of examined nodes.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `pathfinding.shortest_path` | 205 | `count` | Shortest path calculation |

#### `skill`

Skill identifier in the exact Could not find row for … skill.. form, including both trailing dots.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `skill.missing_row` | 113 | `skill` | Skill row missing |

#### `font`

Nonempty typeface in Empty font file … Skipping..., with exact parentheses and ellipsis.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `font.empty` | 45 | `typeface` | Empty font |

#### `clientstring`

INVALID CLIENTSTRING with a letters/digits/underscores identifier.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `clientstring.invalid` | 169 | `key` | Invalid client interface string |

### Network, HTTP, filters and Steam

#### `network`

Instance connections use IPv4 octets 0–255 and port 1–65535; one trailing space is allowed. Async hostnames use lowercase letters, digits, dots and hyphens with nonempty segments. Connected and instance latency contain integer milliseconds. Resyncing is an integer with no assumed unit. Disconnect forms cover unexpected disconnection, realm maintenance and instance connection failure. New types do not automatically extend the selected timeline events. Site-settings SSL failures require the exact cURL/schannel/InitializeSecurityContext chain, a SEC_E_* code, an eight-digit hexadecimal HRESULT and the retry suffix.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `network.instance_connect` | 15 | `host`, `port` | Connecting to a game instance |
| `network.instance_latency` | 16 | `milliseconds` | Game instance latency |
| `network.async_connect` | 17 | `host`, `port` | Asynchronous connection |
| `network.connected` | 18 | `host`, `milliseconds` | Connection established |
| `network.resync` | 131 | `value` | Resynchronization |
| `network.abnormal_disconnect` | 132 | — | Unexpected disconnection |
| `network.maintenance_disconnect` | 203 | — | Disconnected for maintenance |
| `network.instance_disconnect` | 204 | — | Instance disconnection |
| `network.site_settings_ssl_failed` | 247 | `error_code`, `hresult` | SSL failure fetching site settings; the client schedules a retry |

#### `http`

cURL backend; PoE release/tags/N.N.N User-Agent with optional letter suffix and Windows x32/x64. This is client text, not detection of the host OS.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `http.backend` | 87 | `backend` | HTTP implementation |
| `http.user_agent` | 126 | `version`, `bits` | HTTP User-Agent |

#### `filter`

Filter IDs, IPv4, HTTP status 100–599, downloads, saving, reloading and lists. Hashes are nonempty lowercase hexadecimal tokens of variable length; no algorithm or fixed length is assumed. (empty) has a separate form and is also allowed for local_hash. Reload includes true/false, Type Normal and possibly empty Message. A recognized HTTP status does not prove download success.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `filter.resolved` | 90 | `ip` | Item filter address resolved |
| `filter.download` | 91 | `filter_id` | Item filter download |
| `filter.status` | 92 | `filter_id`, `status` | Filter download HTTP status |
| `filter.hash` | 93 | `filter_id`, `hash` | Item filter hash |
| `filter.list_download` | 94 | — | Filter list download |
| `filter.saved` | 128 | `filter_id`, `hash` | Filter saved |
| `filter.reloaded` | 129 | `filter_id`, `result`, `hash`, `type`, `message` | Filter reloaded |
| `filter.empty_hash` | 130 | `filter_id` | Empty filter hash |
| `filter.list_status` | 161 | `status` | Filter list HTTP status |
| `filter.list_resolved` | 162 | `ip` | Filter list address resolved |
| `filter.list_entry` | 163 | `filter_id`, `hash`, `local_hash` | Filter list entry |

#### `steam`

Stats stored; Achivement stored preserving the original typo, with an identifier and optional trailing percent sign; stat failure and exact content recheck notice.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `steam.stats_stored` | 55 | — | Steam statistics stored |
| `steam.achievement` | 158 | `achievement` | Steam achievement |
| `steam.stat_failed` | 159 | `stat` | Failed to store Steam statistic |
| `steam.content_recheck` | 176 | — | Steam content recheck requested |

#### `patch`

Exact request to restart Path of Exile after an update.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `patch.restart_required` | 175 | — | Restart required after update |

#### `daily_deal`

Specific download exception with an HTTP/HTTPS URL and status 100–599. The URL is not opened.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `daily_deal.download_failed` | 171 | `url`, `status` | Daily deal download failed |

### Input, interface and sound

#### `input`

Selected xinputN_N.dll library in the exact Selected XInput.dll message.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `input.xinput_library` | 123 | `library` | XInput library |

#### `ui`

Rebuild UI with numeric mode and an exact input method change notice. Virtual keyboard has mode, default text and title separated by single-quoted delimiters. Text may contain apostrophes. Delimiters and final quote are required; ambiguity uses the first ' and title ' separator. Fields may contain user search text and remain in the local analysis.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `ui.rebuild` | 124 | `mode` | Interface properties rebuilt |
| `ui.virtual_keyboard` | 125 | `mode`, `default_text`, `title` | Virtual keyboard opened |
| `ui.input_method_changed` | 244 | — | Input method changed |

#### `sound`

NUMBER buffer size with B/KB/MB/GB unit, actual/requested channel counts and source count; hexadecimal FMOD version and quoted device name.

| Rule | Priority | Fields | Brief description |
| --- | ---: | --- | --- |
| `sound.buffer` | 164 | `size`, `unit` | Audio buffer |
| `sound.channels` | 165 | `count`, `requested` | Audio channels |
| `sound.sources` | 166 | `count` | Audio sources |
| `sound.fmod_init` | 167 | `version` | FMOD initialization |
| `sound.device` | 168 | `device` | Audio device |
