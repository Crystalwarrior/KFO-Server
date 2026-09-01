/**
 * gm-demo-blocks.js
 * The Blockly visual editor for demo scripts (the Demos tab's "Visual"
 * sub-tab): custom block definitions, the blocks -> script-text generator,
 * the script-text -> blocks importer, and the DemoBlockEditor class that
 * owns a Blockly workspace.
 *
 * Scripts are stored as plain text (today inside an evidence item's `desc`),
 * so everything here is presentation over the scripting language. The block
 * set mirrors the instruction grammar in server/script_runner.py
 * (`parse_demo_description`) and docs/demo_scripting.md, and both directions
 * of conversion key off the exact instruction tuples that parser produces:
 *   ["wait", secs] ["packet", hdr, args] ["command", cmd, arg]
 *   ["set"|"get", name, value] ["concat", name, value, sep]
 *   ["rand", name, low, high] ["save", char, key, value]
 *   ["if", a, op, b, label] ["label", name] ["goto", name] ["return"]
 * That keeps the round trip lossless without re-implementing the parser in
 * JS: text -> blocks uses the server's parsed instructions (either the
 * evidence detail response or POST /api/gm/demos/parse), and blocks -> text
 * re-emits the same grammar.
 *
 * Vendored Blockly: v13.2.1 (RaspberryPiFoundation/blockly release
 * blockly-v13.2.1) in server/web_view/static/vendor/blockly/, plus two
 * plugins from the same repo (commit 1aa51c0ec48f73ca1214397fa70d141ac47a57fe,
 * both v13.1.0) in vendor/blockly/plugins/: @blockly/field-multilineinput
 * (adds the "field_multilinetext" field type used below for multi-line
 * script text) and @blockly/theme-dark (Blockly.Themes.Dark, applied in
 * DemoBlockEditor).
 */

/* --- Block definitions -------------------------------------------------- */

/**
 * Fallback live-state paths for the get block's "insert variable" dropdown,
 * mirroring the reference's "Reading live state: paths" table (gm-demos-tab
 * DEMOS_HELP_HTML; docs/demo_scripting.md). Each entry is inserted verbatim
 * into the get block's PATH field: a bare path like `clients.count` is
 * exactly what the runner's `get <var> <source>` operand grammar accepts
 * (script_runner.py `_resolve_operand` -> `live_get`). Script variables
 * from the workspace are prepended dynamically by demoGetInsertOptions -- a
 * bare variable name copies the variable's current value.
 *
 * This static list is only a stopgap: the Demos tab replaces it with the
 * server-generated menu (scripting.py `live_path_menu`, served at
 * GET /api/gm/demos/paths -> DemoBlockEditor.setInsertPathOptions), so every
 * whitelisted path the runner actually accepts can be inserted -- not just
 * this hand-picked fifteen. The fallback stays in force on pages that load
 * this file standalone (e.g. the Blockly smoke test) or when the panel API
 * is unreachable.
 *
 * Must be declared before DEMO_BLOCK_DEFS: the get block's JSON spreads it
 * while the array literal is evaluated.
 */
let DEMO_INSERT_PATH_OPTIONS = [
    'clients.count',
    'client[0].showname',
    'client[0].char_name',
    'client[0].char_id',
    'client[0].pos',
    'afk[0].showname',
    'timer[0].remaining_ms',
    'timer[1].remaining_ms',
    'evidence[0].name',
    'evidence[0].desc',
    'links[0].target',
    'area.name',
    'area.background',
    'area.music',
    'hub.name',
].map((p) => [p, p]);

/**
 * Colour hues follow Blockly's own category palette so the toolbox matches
 * the blocks: control = blue, variables = magenta, packets = orange,
 * commands = green.
 */
const DEMO_BLOCK_DEFS = [
    // --- Control ---
    {
        type: 'demo_wait',
        message0: 'wait %1 ms',
        args0: [{ type: 'field_number', name: 'MS', value: 1000, min: 0 }],
        previousStatement: null,
        nextStatement: null,
        colour: 210,
        tooltip: 'Pause the script for this many milliseconds (1000 ms = 1 second).',
    },
    {
        type: 'demo_if',
        message0: 'if %1 %2 %3',
        message1: 'then jump to label %1',
        args0: [
            { type: 'field_input', name: 'A', text: '' },
            {
                type: 'field_dropdown',
                name: 'OP',
                options: [
                    ['==', '=='], ['!=', '!='], ['<', '<'], ['<=', '<='], ['>', '>'], ['>=', '>='],
                ],
            },
            { type: 'field_input', name: 'B', text: '' },
        ],
        args1: [
            { type: 'field_input', name: 'LABEL', text: '' },
        ],
        previousStatement: null,
        nextStatement: null,
        colour: 210,
        tooltip: 'Jump to the label when the comparison is true. Both sides can be a number, expression, variable or live path.',
    },
    {
        type: 'demo_label',
        message0: 'label %1',
        args0: [{ type: 'field_input', name: 'NAME', text: '' }],
        previousStatement: null,
        nextStatement: null,
        colour: 210,
        tooltip: 'Mark a spot in the script. Labels are targets for goto and if blocks.',
    },
    {
        type: 'demo_goto',
        message0: 'goto label %1',
        args0: [{ type: 'field_input', name: 'NAME', text: '' }],
        previousStatement: null,
        nextStatement: null,
        colour: 210,
        tooltip: 'Jump to a label, remembering where you came from. A later "return" block jumps back here.',
    },
    {
        type: 'demo_return',
        message0: 'return',
        previousStatement: null,
        nextStatement: null,
        colour: 210,
        tooltip: 'Jump back to the matching goto. If there is nothing to return to, the script just ends.',
    },

    // --- Variables ---
    {
        type: 'demo_set',
        message0: 'set %1 = %2',
        args0: [
            { type: 'field_variable', name: 'VAR', variable: 'x' },
            { type: 'field_input', name: 'VALUE', text: '' },
        ],
        previousStatement: null,
        nextStatement: null,
        colour: 330,
        tooltip: 'Store a value in a variable: a number or math expression (5, gold*2+5), a quoted string ("Hello there"), or another variable.',
    },
    {
        type: 'demo_get',
        message0: 'get %1 = %2',
        message1: 'insert %1',
        args0: [
            { type: 'field_variable', name: 'VAR', variable: 'x' },
            { type: 'field_input', name: 'PATH', text: '' },
        ],
        args1: [
            // "Insert variable…" dropdown: picking an entry replaces the
            // PATH field with the bare path or variable name. Options are
            // refreshed from the workspace's variables + curated live paths
            // by demoRefreshGetInsertOptions; the static list below is the
            // fallback for fresh blocks before that first refresh.
            {
                type: 'field_dropdown',
                name: 'INSERT_VAR',
                options: [['Insert variable…', ''], ...DEMO_INSERT_PATH_OPTIONS],
            },
        ],
        previousStatement: null,
        nextStatement: null,
        colour: 330,
        tooltip: 'Read live server state into a variable. Examples: players, clients.count, client[0].showname, evidence[i].name, timer[1].remaining_ms, area.background, hub.name, char["Phoenix"].title.',
    },
    {
        type: 'demo_concat',
        message0: 'concat %1 %2',
        message1: 'separator %1 (optional)',
        args0: [
            { type: 'field_variable', name: 'VAR', variable: 'x' },
            { type: 'field_input', name: 'VALUE', text: '' },
        ],
        args1: [
            { type: 'field_input', name: 'SEP', text: '' },
        ],
        previousStatement: null,
        nextStatement: null,
        colour: 330,
        tooltip: 'Add text to the end of a string variable. The separator only appears between items, so a list never starts or ends with it.',
    },
    {
        type: 'demo_rand',
        message0: 'rand %1 from %2 to %3',
        args0: [
            { type: 'field_variable', name: 'VAR', variable: 'x' },
            { type: 'field_input', name: 'MIN', text: '1' },
            { type: 'field_input', name: 'MAX', text: '6' },
        ],
        previousStatement: null,
        nextStatement: null,
        colour: 330,
        tooltip: 'Store a random whole number between min and max, both ends included. Bounds can be numbers, expressions or variables.',
    },
    {
        type: 'demo_save',
        message0: 'save %1 %2 = %3',
        args0: [
            { type: 'field_input', name: 'CHAR', text: '0' },
            { type: 'field_input', name: 'KEY', text: '' },
            { type: 'field_input', name: 'VALUE', text: '' },
        ],
        previousStatement: null,
        nextStatement: null,
        colour: 330,
        tooltip: 'Persist a value into a character\'s saved data (config/character_data.yaml). CHAR is a character id (the /charids number) or a quoted folder name like "Phoenix". Survives restarts and is shared across the hub.',
    },

    // --- Packets ---
    {
        type: 'demo_packet',
        message0: 'send %1 packet',
        message1: '%1',
        args0: [
            {
                type: 'field_dropdown',
                name: 'HDR',
                options: [
                    ['MS (IC message)', 'MS'], ['CT (OOC message)', 'CT'], ['MC (music)', 'MC'],
                    ['BN (background)', 'BN'], ['HP (penalties)', 'HP'], ['RT (testimony/anim)', 'RT'],
                    ['JD (judge controls)', 'JD'], ['GM (game mode)', 'GM'], ['ST (subtheme)', 'ST'],
                ],
            },
        ],
        args1: [
            { type: 'field_input', name: 'FIELDS', text: '' },
        ],
        previousStatement: null,
        nextStatement: null,
        colour: 20,
        tooltip: 'Broadcast an AO packet. Type the fields after the header, separated by #, exactly like the packet line in a script.',
    },
    {
        type: 'demo_packet_ct',
        message0: 'CT message (OOC)',
        message1: 'narrator %1',
        message2: 'message %1',
        message3: 'sfx %1',
        args1: [
            { type: 'field_input', name: 'NAME', text: 'narrator' },
        ],
        args2: [
            // field_multilinetext: multi-line OOC message. Enter commits,
            // Shift+Enter inserts a newline.
            { type: 'field_multilinetext', name: 'MSG', text: '' },
        ],
        args3: [
            { type: 'field_input', name: 'SFX', text: '0' },
        ],
        previousStatement: null,
        nextStatement: null,
        colour: 20,
        tooltip: 'Send an OOC (CT) message to everyone in the area. Use <!var> inside the message to drop in a variable or live path.',
    },
    {
        type: 'demo_packet_mc',
        message0: 'MC music',
        message1: 'song %1',
        message2: 'loop %1   effects %2',
        args1: [
            { type: 'field_input', name: 'SONG', text: '' },
        ],
        args2: [
            { type: 'field_checkbox', name: 'LOOP', checked: true },
            { type: 'field_number', name: 'FX', value: 0, min: 0 },
        ],
        previousStatement: null,
        nextStatement: null,
        colour: 20,
        tooltip: 'Play a music track (MC packet). Music only reaches clients currently in the area; use /play for a persistent change.',
    },
    {
        type: 'demo_packet_bn',
        message0: 'BN background %1',
        args0: [{ type: 'field_input', name: 'BG', text: '' }],
        previousStatement: null,
        nextStatement: null,
        colour: 20,
        tooltip: 'Change the background (BN packet) for everyone in the area. Use /bg for a persistent change that new arrivals also see.',
    },
    {
        // Full IC message (MS) packet in the SERVER -> CLIENT layout,
        // field-for-field with what area.send_ic actually broadcasts
        // (aoprotocol.py's net_cmd_ms parses the different CLIENT -> SERVER
        // field order, but demos broadcast raw via area.send_command, so
        // clients read the fields in the server order -- docs/demo_scripting.md:
        // "if choosing between Client and Server version of the packet, use
        // the Server packet"). Wire values the server always fills (msg_type,
        // charid_pair, offset_pair, sfx_looping) are validated below; the
        // pairing fields (other_*, third_*) are legitimately blank when no
        // one is paired, and folder/pos/sfx/frames_*/effect may be empty for
        // narration (a blank pos even inherits the area's last IC message
        // position).
        type: 'demo_packet_ms',
        message0: 'MS (IC message)',
        message1: 'msg_type %1   pre %2   folder %3   anim %4',
        message2: 'text %1',
        message3: 'pos %1   sfx %2   emote_mod %3   cid %4   sfx_delay %5   button %6   evidence %7',
        message4: 'flip %1   ding %2   color %3   showname %4   charid_pair %5   other_folder %6',
        message5: 'other_emote %1   offset_pair %2   other_offset %3   other_flip %4   nonint_pre %5   sfx_looping %6',
        message6: 'screenshake %1   frames_shake %2   frames_realization %3   frames_sfx %4   additive %5   effect %6',
        message7: 'third_charid %1   third_folder %2   third_emote %3   third_offset %4   third_flip %5   video %6',
        args1: [
            { type: 'field_dropdown', name: 'MSG_TYPE', options: [
                    ['Desk Hide', '0'],
                    ['Desk Show', '1'],
                    ['Desk Emote Only', '2'],
                    ['Desk Pre Only', '3'],
                    ['Desk Emote Only Ex.', '4'],
                    ['Desk Pre Only Ex.', '5'],
                ],
            },
            { type: 'field_input', name: 'PRE', text: '' },
            { type: 'field_input', name: 'FOLDER', text: '' },
            { type: 'field_input', name: 'ANIM', text: '' },
        ],
        args2: [
            // field_multilinetext: multi-line IC text, alone on its own line
            // (Message 2 is the "text" argument of the MS packet). Enter
            // commits, Shift+Enter inserts a newline.
            { type: 'field_multilinetext', name: 'TEXT', text: '' },
        ],
        args3: [
            { type: 'field_input', name: 'POS', text: '' },
            { type: 'field_input', name: 'SFX', text: '' },
            { type: 'field_dropdown', name: 'EMOTE_MOD', options: [
                    ['Idle', '0'],
                    ['Pre-Animation', '1'],
                    ['Zoom', '5'],
                    ['Zoom Pre-Animation', '6'],
                ],
            },
            { type: 'field_number', name: 'CID', value: -1 },
            { type: 'field_number', name: 'SFX_DELAY', value: 0 },
            { type: 'field_input', name: 'BUTTON', text: '0' },
            { type: 'field_number', name: 'EVIDENCE', value: -1 },
        ],
        args4: [
            { type: 'field_checkbox', name: 'FLIP', checked: false },
            { type: 'field_checkbox', name: 'DING', checked: false },
            { type: 'field_number', name: 'COLOR', value: 0, min: 0 },
            { type: 'field_input', name: 'SHOWNAME', text: '' },
            { type: 'field_input', name: 'CHARID_PAIR', text: '-1' },
            { type: 'field_input', name: 'OTHER_FOLDER', text: '' },
        ],
        args5: [
            { type: 'field_input', name: 'OTHER_EMOTE', text: '' },
            { type: 'field_input', name: 'OFFSET_PAIR', text: '0' },
            { type: 'field_input', name: 'OTHER_OFFSET', text: '0' },
            { type: 'field_checkbox', name: 'OTHER_FLIP', checked: false },
            { type: 'field_checkbox', name: 'NONINT_PRE', checked: false },
            { type: 'field_checkbox', name: 'SFX_LOOPING', checked: false },
        ],
        args6: [
            { type: 'field_checkbox', name: 'SCREENSHAKE', checked: false },
            { type: 'field_input', name: 'FRAMES_SHAKE', text: '' },
            { type: 'field_input', name: 'FRAMES_REALIZATION', text: '' },
            { type: 'field_input', name: 'FRAMES_SFX', text: '' },
            { type: 'field_checkbox', name: 'ADDITIVE', checked: false },
            { type: 'field_input', name: 'EFFECT', text: '' },
        ],
        args7: [
            { type: 'field_number', name: 'THIRD_CHARID', value: -1 },
            { type: 'field_input', name: 'THIRD_FOLDER', text: '' },
            { type: 'field_input', name: 'THIRD_EMOTE', text: '' },
            { type: 'field_input', name: 'THIRD_OFFSET', text: '' },
            { type: 'field_checkbox', name: 'THIRD_FLIP', checked: false },
            { type: 'field_input', name: 'VIDEO', text: '' },
        ],
        previousStatement: null,
        nextStatement: null,
        colour: 20,
        tooltip: 'Broadcast an IC (MS) message using the server-to-client layout (the exact field order the server itself broadcasts -- demos bypass the client parser). Fill at least msg_type, folder, text and pos; other_folder/other_emote/offset_pair/other_offset/other_flip are for pairing, third_* for a third character, both blank when unused. Leave pos blank for narration -- the demo runner reuses the area\'s last IC message position. Use <!var> inside text/showname to drop in a variable. Color: 0=White, 1=Green, 2=Orange, 3=Red, 4=Blue, 5=Cyan, 6=Purple, 7=Yellow, 8=Grey; 9+ are custom client-side colors.',
    },
    {
        // HP penalty bars: HP#<side:int>#<val:int>#% (aoprotocol net_cmd_hp;
        // area.change_hp: side 1 = defense, 2 = prosecution; value 0-10).
        // Broadcast only -- the area's hp_def/hp_pro state is untouched.
        type: 'demo_packet_hp',
        message0: 'HP: set %1 penalties to %2',
        args0: [
            {
                type: 'field_dropdown',
                name: 'SIDE',
                options: [['defense', '1'], ['prosecution', '2']],
            },
            { type: 'field_number', name: 'VAL', value: 0, min: 0, max: 10 },
        ],
        previousStatement: null,
        nextStatement: null,
        colour: 20,
        tooltip: 'Set a penalty bar (HP packet): defense or prosecution, 0 to 10. Only broadcasts to the area -- for a persistent change use the /hp command.',
    },
    {
        // Judge sign (WT/CE/JR): RT#<type:string>#% with an optional integer
        // second arg (aoprotocol net_cmd_rt; the server itself sends
        // RT#testimony1#1 when a recorded testimony ends). The type is a free
        // text field on purpose: demos broadcast RT raw, so clients accept
        // completely custom animation names, not just the three standard
        // signs (net_cmd_rt's own whitelist only applies to client->server).
        type: 'demo_packet_rt',
        message0: 'RT: %1%2',
        args0: [
            { type: 'field_input', name: 'TYPE', text: 'testimony1' },
            { type: 'field_input', name: 'ARG', text: '' },
        ],
        previousStatement: null,
        nextStatement: null,
        colour: 20,
        tooltip: 'Play a judge sign animation (RT packet). Standard signs: testimony1 (WT), testimony2 (CE), judgeruling (JR) -- or type any custom animation name your clients support. The second field is optional: leave it blank for a plain RT, or set it to a number (the server sends RT#testimony1#1 when a recorded testimony ends).',
    },
    {
        // Judge button permissions: JD#<value:int>#%. Server -> client only
        // (area.update_judge_buttons): 1 = grant judge buttons, 0 = hide
        // them, -1 = restore the client's own default.
        type: 'demo_packet_jd',
        message0: 'JD: %1 judge buttons',
        args0: [
            {
                type: 'field_dropdown',
                name: 'MODE',
                options: [
                    ['grant (show)', '1'],
                    ['hide', '0'],
                    ['client default', '-1'],
                ],
            },
        ],
        previousStatement: null,
        nextStatement: null,
        colour: 20,
        tooltip: 'Show or hide the judge buttons (JD packet) for everyone in the area: grant forces them on, hide forces them off, client default lets each player decide.',
    },

    // --- Commands ---
    {
        type: 'demo_command',
        message0: 'run command /%1',
        // field_multilinetext: commands can carry multi-line arguments (demo
        // scripts are line-based, but the block importer preserves newlines
        // inside quoted values). Enter commits, Shift+Enter inserts a newline.
        args0: [{ type: 'field_multilinetext', name: 'CMD', text: '' }],
        previousStatement: null,
        nextStatement: null,
        colour: 160,
        tooltip: 'Run any OOC command exactly as if a user typed it, e.g. "timer 1 5m start", "bg BOTC-TownSquare", "pos_lock wit".',
    },
];

// Register the multiline-input field plugin (vendor/blockly/plugins/
// field_multilineinput_compressed.js, loaded before this file). The plugin
// ships an explicit register function; without it, block definitions naming
// the "field_multilinetext" type would only fail later, when a block is
// created from JSON ("Unable to find [field_multilinetext] in the
// registry"). Fail loudly here instead.
if (typeof registerFieldMultilineInput !== 'function') {
    throw new Error('Blockly field-multilineinput plugin not loaded: /static/vendor/blockly/plugins/field_multilineinput_compressed.js must load before gm-demo-blocks.js.');
}
registerFieldMultilineInput();

// The plugin elides lines longer than maxDisplayLength (50 chars, inherited
// from Blockly.Field) with "...". Demo script text should stay fully visible
// on the block -- that's the whole point of the multiline fields -- so give
// every field the plugin creates the same "never elide" treatment Blockly's
// own FieldLabel uses (maxDisplayLength = Infinity). Fields are always
// created through the static fromJson (block definitions and toolbox alike),
// so wrapping it covers every instance. Only the rendered read-out and width
// measurement are affected; editing and serialization are untouched.
const _FMIFromJson = FieldMultilineInput.fromJson;
FieldMultilineInput.fromJson = function (options) {
    const field = _FMIFromJson.call(this, options);
    field.maxDisplayLength = Infinity;
    return field;
};

Blockly.common.defineBlocksWithJsonArray(DEMO_BLOCK_DEFS);

/* --- Toolbox ------------------------------------------------------------ */

const DEMO_TOOLBOX = {
    kind: 'categoryToolbox',
    contents: [
        {
            kind: 'category',
            name: 'Control',
            colour: '210',
            contents: [
                { kind: 'block', type: 'demo_wait' },
                { kind: 'block', type: 'demo_if' },
                { kind: 'block', type: 'demo_label' },
                { kind: 'block', type: 'demo_goto' },
                { kind: 'block', type: 'demo_return' },
            ],
        },
        {
            kind: 'category',
            name: 'Variables',
            colour: '330',
            contents: [
                // Baseline contents only: demoRefreshVariablesFlyout() pushes
                // the live variable map into this category the first time the
                // Visual sub-tab opens (and on every variable
                // create/rename/delete), prepending one set/get block pair per
                // variable -- the same behavior as Blockly's own Variables
                // category -- while the generic set/get (a failsafe that
                // defaults to "x") and the other blocks stay at the end. The
                // "Create variable…" button callback is registered in
                // DemoBlockEditor.ensure() via the toolbox callback API.
                { kind: 'button', text: 'Create variable…', callbackKey: 'CREATE_VARIABLE' },
                { kind: 'block', type: 'demo_set' },
                { kind: 'block', type: 'demo_get' },
                { kind: 'block', type: 'demo_concat' },
                { kind: 'block', type: 'demo_rand' },
                { kind: 'block', type: 'demo_save' },
            ],
        },
        {
            kind: 'category',
            name: 'Packets',
            colour: '20',
            contents: [
                { kind: 'block', type: 'demo_packet_ms' },
                { kind: 'block', type: 'demo_packet_hp' },
                { kind: 'block', type: 'demo_packet_rt' },
                { kind: 'block', type: 'demo_packet_jd' },
                { kind: 'block', type: 'demo_packet' },
                { kind: 'block', type: 'demo_packet_ct' },
                { kind: 'block', type: 'demo_packet_mc' },
                { kind: 'block', type: 'demo_packet_bn' },
            ],
        },
        {
            kind: 'category',
            name: 'Commands',
            colour: '160',
            // Collapsible so the catalog's per-module sub-categories render
            // as a tree (Blockly only nests categories under a collapsible
            // parent); the static toolbox carries just the free-form
            // fallback until the command catalog lands.
            collapsible: 'true',
            expanded: 'true',
            contents: [
                { kind: 'block', type: 'demo_command' },
            ],
        },
    ],
};

/**
 * Rebuild the Variables category flyout contents from the workspace's live
 * variable list, mirroring Blockly's own dynamic variables category
 * (Variables.flyoutCategory): a "Create variable…" button, then one
 * set/get block pair per variable -- each chip already bound to that
 * variable (the `{ name, type }` JSON reference is the exact format
 * Blockly's built-in variable chips use) -- and finally the generic blocks
 * that don't need their own chip, since their VAR dropdown lists every
 * variable anyway. The generic set/get blocks are kept as a failsafe:
 * block definitions default them to the variable "x", so set/get blocks are
 * always available even when the variable map is empty or in a weird state
 * (dragging one creates "x" if it doesn't exist, which can then be renamed
 * or re-picked in the dropdown).
 */
function demoVariableCategoryContents(workspace) {
    const contents = [
        { kind: 'button', text: 'Create variable…', callbackKey: 'CREATE_VARIABLE' },
    ];
    const variables = workspace.getVariableMap()
        .getVariablesOfType('')
        .sort(Blockly.Variables.compareByName);
    variables.forEach((v) => {
        const fields = { VAR: { name: v.name, type: v.type } };
        contents.push(
            { kind: 'block', type: 'demo_set', gap: 8, fields },
            { kind: 'block', type: 'demo_get', gap: 8, fields },
        );
    });
    contents.push(
        { kind: 'block', type: 'demo_set', gap: 8 },
        { kind: 'block', type: 'demo_get', gap: 8 },
        { kind: 'block', type: 'demo_concat', gap: 8 },
        { kind: 'block', type: 'demo_rand', gap: 8 },
        { kind: 'block', type: 'demo_save', gap: 8 },
    );
    return contents;
}

/**
 * Push the current variable map into the toolbox's Variables category and,
 * if that category's flyout is open, re-render it in place.
 *
 * This uses ToolboxCategory.updateFlyoutContents() -- a public API for
 * exactly this case, with refreshSelection() to re-show the open flyout.
 * workspace.updateToolbox() would also work but it rebuilds the whole
 * toolbox DOM, hides the flyout, and leaves an already-open category stale
 * until the user switches tabs and back (which is the bug this avoids).
 */
function demoRefreshVariablesFlyout(workspace) {
    const toolbox = workspace.getToolbox && workspace.getToolbox();
    if (!toolbox) return;
    const items = (typeof toolbox.getToolboxItems === 'function') ? toolbox.getToolboxItems() : [];
    const category = items.find((item) => (
        typeof item.getName === 'function'
        && item.getName() === 'Variables'
        && typeof item.updateFlyoutContents === 'function'
    ));
    if (!category) return;
    category.updateFlyoutContents(demoVariableCategoryContents(workspace));
    if (
        typeof toolbox.refreshSelection === 'function'
        && toolbox.getSelectedItem && toolbox.getSelectedItem() === category
    ) {
        // Re-render the flyout immediately if the Variables category is the
        // one showing, so a just-created variable appears without any tab
        // switch.
        toolbox.refreshSelection();
    }
}

/* --- Get block "insert variable" dropdown ------------------------------- */

/**
 * Build the get block's "insert variable" dropdown options for a workspace:
 * the placeholder, then the workspace's script variables, then the live
 * paths (DEMO_INSERT_PATH_OPTIONS, declared above the block defs; replaced
 * by the server-generated menu via demoSetInsertPathOptions).
 * Every entry is inserted into PATH as the bare name -- for a get operand
 * the wrapped `<!name>` form is not a valid source (script_runner.py
 * resolves `get`'s second operand as a live path or plain value).
 */
function demoGetInsertOptions(workspace) {
    const options = [['Insert variable…', '']];
    workspace.getVariableMap()
        .getVariablesOfType('')
        .sort(Blockly.Variables.compareByName)
        .forEach((v) => options.push([v.name, v.name]));
    options.push(...DEMO_INSERT_PATH_OPTIONS);
    return options;
}

/**
 * Replace the curated live-path menu offered by every get block's "insert
 * variable" dropdown with a server-generated one. `paths` are bare path
 * strings exactly as `get <var> <source>` accepts them (see
 * server/scripting.py `live_path_menu`). The Demos tab calls this with the
 * GET /api/gm/demos/paths payload once it loads; until then (and on error),
 * DEMO_INSERT_PATH_OPTIONS above remains in force. Any get blocks already
 * in a workspace get their dropdown rebuilt in place via the same refresh
 * path variable create/delete uses -- setOptions preserves each block's
 * current (placeholder) value, so no change events fire.
 */
function demoSetInsertPathOptions(workspace, paths) {
    if (Array.isArray(paths)) {
        DEMO_INSERT_PATH_OPTIONS = paths.map((p) => [p, p]);
    }
    if (workspace) demoRefreshGetInsertOptions(workspace);
}

/**
 * Rebuild every get block's "insert variable" dropdown from the current
 * variable map (and the live-path list). Called when a script loads, on
 * variable create/rename/delete, and on block create (so toolbox-dragged
 * get blocks pick up the workspace's variables too). setOptions only
 * replaces the menu contents -- the current (empty) value is untouched, so
 * no change events fire.
 */
function demoRefreshGetInsertOptions(workspace) {
    const options = demoGetInsertOptions(workspace);
    workspace.getAllBlocks(false).forEach((b) => {
        if (b.type !== 'demo_get') return;
        const field = b.getField('INSERT_VAR');
        if (field && typeof field.setOptions === 'function') {
            field.setOptions(options);
        }
    });
}

/* --- Commands toolbox (dynamic) ------------------------------------------ */

/**
 * Server-generated command catalog for the Commands toolbox category: one
 * entry per command a demo may run, from GET /api/gm/demos/commands
 * (CommandLister minus mod-only commands). Each entry is
 * `{name, module, summary, usage, permission, args:[{name, type, required,
 * default, choices, rest, variadic, help}]}`. Populated by
 * demoSetCommandCatalog; the toolbox renders one block per command whose
 * fields mirror the `@command(...)` Arg declarations, grouped into
 * collapsible per-module sub-categories (Blockly's `collapsible` tree
 * feature -- v13's flyout has no category inflater, so the nesting lives
 * in the toolbox itself and is applied by rebuilding the toolbox when the
 * catalog lands).
 */
let DEMO_COMMAND_CATALOG = [];

/** Whether the per-module command sub-categories start expanded. */
let DEMO_COMMANDS_EXPANDED = true;

/**
 * Build one Blockly field for a catalogued command arg. Fields are named
 * ARG_0..ARG_N in declaration order so the shared generator can walk them
 * without knowing the command. Mapping: choices -> dropdown, bool ->
 * checkbox (emitted as on/off), int -> number field, everything else
 * (str, custom converters, rest, variadic) -> text field.
 */
function demoCommandArgField(arg, idx) {
    const name = `ARG_${idx}`;
    if (arg.choices && arg.choices.length) {
        const options = arg.choices.map((c) => [String(c), String(c)]);
        const def = (arg.default === null || arg.default === undefined) ? null : String(arg.default);
        const field = { type: 'field_dropdown', name, options };
        if (def !== null && options.some((o) => o[1] === def)) field.value = def;
        return field;
    }
    if (arg.type === 'bool') {
        return { type: 'field_checkbox', name, checked: !!arg.default };
    }
    if (arg.type === 'int') {
        const dv = Number(arg.default);
        return { type: 'field_number', name, value: Number.isFinite(dv) ? dv : 0 };
    }
    return {
        type: 'field_input',
        name,
        text: (arg.default === null || arg.default === undefined) ? '' : String(arg.default),
    };
}

/** Tooltip for one command block: summary, usage line, then each arg's help. */
function demoCommandBlockTooltip(cmd) {
    const lines = [];
    if (cmd.summary) lines.push(cmd.summary);
    if (cmd.usage) lines.push(cmd.usage);
    (cmd.args || []).forEach((a) => {
        const req = a.required ? '' : ' (optional)';
        lines.push(`${a.name}${req}${a.help ? `: ${a.help}` : ''}`);
    });
    return lines.join('\n');
}

/** Block definition for one catalogued command (`/name arg1 arg2 ...`). */
function demoCommandBlockDef(name, cmd) {
    const args = cmd.args || [];
    const fields = args.map(demoCommandArgField);
    const placeholders = args.map((_, i) => `%${i + 1}`).join(' ');
    const def = {
        type: `demo_cmd_${name}`,
        message0: `/${name}${placeholders ? ` ${placeholders}` : ''}`,
        previousStatement: null,
        nextStatement: null,
        colour: 160,
        tooltip: demoCommandBlockTooltip(cmd),
    };
    if (fields.length) def.args0 = fields;
    return def;
}

/**
 * Shared generator for every `demo_cmd_*` block: reads ARG_0..ARG_N in
 * declaration order (from the catalog) and re-emits `/name arg1 arg2 ...`
 * with the mandatory `%` line terminator (a command line only ends at `%`
 * -- newlines are content, so omitting it would swallow the rest of the
 * script into this one command). Bools become on/off, values with
 * whitespace are quoted, and a variadic list is split into
 * individually-quoted tokens so it doesn't collapse into one argument.
 * Rest args stay bare: they capture the raw remainder of the line either
 * way, and quoting them would break the text -> blocks round trip (the
 * script parser would hand the quotes back). Empty optional args are
 * dropped.
 */
function demoCommandBlockGenerator(block) {
    const name = block.type.slice('demo_cmd_'.length);
    const meta = (DEMO_COMMAND_CATALOG.find((c) => c.name === name) || {}).args || [];
    const parts = [];
    for (let i = 0; i < meta.length; i++) {
        const field = block.getField(`ARG_${i}`);
        if (!field) break;
        let value = field.getValue();
        if (typeof value === 'boolean') value = value ? 'on' : 'off';
        value = String(value);
        if (!value) continue;
        if (meta[i].variadic) {
            value.split(/\s+/).filter(Boolean)
                .forEach((tok) => parts.push(quoteDemoOperand(escapeDemoText(tok))));
        } else if (meta[i].rest) {
            parts.push(escapeDemoText(value));
        } else {
            parts.push(quoteDemoOperand(escapeDemoText(value)));
        }
    }
    return (parts.length ? `/${name} ${parts.join(' ')}` : `/${name}`) + '%';
}

/**
 * Build the full category-toolbox definition with the command catalog baked
 * into the Commands category: per-module collapsible sub-categories
 * (Blockly's native `collapsible` tree -- v13.2.1's flyout has no category
 * inflater, so nesting must live at the toolbox level, and nested items
 * only materialize under a collapsible parent), plus Expand/Collapse-all
 * flyout buttons and the free-form `demo_command` block as a failsafe. The
 * other categories are copied from the static DEMO_TOOLBOX untouched.
 */
function demoCommandToolboxDef() {
    const byModule = new Map();
    DEMO_COMMAND_CATALOG.forEach((cmd) => {
        const module = cmd.module || 'other';
        if (!byModule.has(module)) byModule.set(module, []);
        byModule.get(module).push({ kind: 'block', type: `demo_cmd_${cmd.name}` });
    });
    const moduleCategories = [...byModule.entries()]
        .sort((a, b) => a[0].localeCompare(b[0]))
        .map(([module, blocks]) => ({
            kind: 'category',
            name: module,
            colour: '160',
            collapsible: 'true',
            expanded: DEMO_COMMANDS_EXPANDED ? 'true' : 'false',
            contents: blocks,
        }));
    const commandsCategory = {
        kind: 'category',
        name: 'Commands',
        colour: '160',
        collapsible: 'true',
        expanded: 'true',
        contents: [
            ...moduleCategories,
            { kind: 'block', type: 'demo_command', gap: 12 },
        ],
    };
    return {
        kind: 'categoryToolbox',
        contents: DEMO_TOOLBOX.contents
            .filter((c) => !c || c.name !== 'Commands')
            .concat(commandsCategory),
    };
}

/**
 * Apply the command catalog to the toolbox: rebuild it so the Commands
 * category gains its collapsible per-module sub-categories. updateToolbox()
 * is the only API that creates child toolbox items with DOM
 * (updateFlyoutContents only builds flyout items, so nested categories
 * added that way would never render); it re-creates every category, so the
 * Variables chips and get-block dropdowns are reapplied afterwards.
 */
function demoRefreshCommandsToolbox(workspace) {
    if (!workspace || !DEMO_COMMAND_CATALOG.length) return;
    if (typeof workspace.updateToolbox !== 'function') return;
    workspace.updateToolbox(demoCommandToolboxDef());
    demoRefreshVariablesFlyout(workspace);
    demoRefreshGetInsertOptions(workspace);
}

/**
 * Install the server's command catalog. Safe to call before the workspace
 * exists: the block definitions are registered and the toolbox rebuild
 * happens when the workspace is created. Re-calling with a fresh catalog
 * (e.g. after /refresh) redefines the blocks and rebuilds in place.
 */
function demoSetCommandCatalog(workspace, commands) {
    if (!Array.isArray(commands)) return;
    DEMO_COMMAND_CATALOG = commands;
    const defs = [];
    commands.forEach((cmd) => {
        const name = String(cmd.name || '').replace(/[^a-z0-9_]/gi, '_');
        if (!name) return;
        defs.push(demoCommandBlockDef(name, cmd));
        demoGenerator.forBlock[`demo_cmd_${name}`] = demoCommandBlockGenerator;
    });
    if (defs.length) {
        Blockly.common.defineBlocksWithJsonArray(defs);
    }
    demoRefreshCommandsToolbox(workspace);
}

/**
 * Expand or collapse every command sub-category. The buttons live in the
 * Commands flyout; they walk the collapsible category's child toolbox
 * items directly (setExpanded), so no toolbox rebuild is needed and the
 * open flyout survives. Toggling also updates the default the next
 * toolbox rebuild uses.
 */
function demoSetCommandsExpanded(workspace, expanded) {
    DEMO_COMMANDS_EXPANDED = !!expanded;
    const toolbox = workspace && workspace.getToolbox && workspace.getToolbox();
    if (!toolbox) return;
    const items = (typeof toolbox.getToolboxItems === 'function') ? toolbox.getToolboxItems() : [];
    const commands = items.find((item) => (
        typeof item.getName === 'function' && item.getName() === 'Commands'
    ));
    // Only a collapsible parent materializes its children as toolbox items.
    if (!commands || typeof commands.getChildToolboxItems !== 'function') return;
    commands.getChildToolboxItems().forEach((child) => {
        if (child && typeof child.setExpanded === 'function') {
            child.setExpanded(expanded);
        }
    });
}

/**
 * Best-effort map of a parsed command instruction back to its per-arg block.
 * The server parser splits a command line on plain spaces (script_runner.py
 * parse_demo_description), so tokenizing the same way and validating each
 * token against the arg spec keeps the round trip lossless. Anything that
 * doesn't fit -- unknown command, quoted-with-space token, wrong type,
 * too few/too many tokens -- falls back to the free-form demo_command block.
 */
function mapDemoCommandToBlock(meta, name, argText) {
    const generic = { type: 'demo_command', fields: { CMD: argText ? `${name} ${argText}` : name } };
    if (!meta) return generic;
    const args = meta.args || [];
    const tokens = argText.trim() ? argText.trim().split(/\s+/) : [];
    const tokenOk = (tok, spec) => {
        if (tok.includes('"') || tok.includes("'")) return false; // a split quoted value
        if (spec.choices && spec.choices.length) {
            return spec.choices.some((c) => String(c).toLowerCase() === tok.toLowerCase());
        }
        if (spec.type === 'int') return /^-?\d+$/.test(tok);
        if (spec.type === 'bool') return /^(on|off|true|false|1|0|yes|no)$/i.test(tok);
        return true;
    };
    const values = [];
    let ti = 0;
    for (const spec of args) {
        if (spec.rest) {
            values.push(argText.trim());
            ti = tokens.length;
        } else if (spec.variadic) {
            const rest = tokens.slice(ti);
            if (!rest.length && spec.required) return generic;
            if (rest.some((t) => !tokenOk(t, spec))) return generic;
            values.push(rest.join(' '));
            ti = tokens.length;
        } else {
            if (ti >= tokens.length) {
                if (spec.required) return generic;
                values.push('');
            } else {
                const tok = tokens[ti++];
                if (!tokenOk(tok, spec)) return generic;
                values.push(tok);
            }
        }
    }
    if (ti < tokens.length) return generic; // too many tokens
    const fields = {};
    values.forEach((v, i) => { fields[`ARG_${i}`] = v; });
    return { type: `demo_cmd_${name}`, fields };
}

/* --- Text helpers ------------------------------------------------------- */

/**
 * Escape a piece of script text so it survives the server parser's unescape
 * step (`<num>` -> `#`, `<and>` -> `&`, `<percent>` -> `%`, `<dollar>` -> `$`,
 * see parse_demo_description). Used for instruction-line operands (set/get/
 * concat/rand/save values, if operands, label/goto names, commands): there
 * `#`/`&`/`$` round-trip fine inside quoted values. A literal `%` cannot be
 * represented in script text at all -- the parser unescapes `<percent>` to
 * `%` before splitting lines, so it always ends the line early (see
 * tests/test_automation.py's test_parse_demo_description_unescapes). The
 * validator warns about it.
 */
function escapeDemoText(text) {
    return String(text)
        .replace(/&/g, '<and>')
        .replace(/#/g, '<num>')
        .replace(/%/g, '<percent>')
        .replace(/\$/g, '<dollar>');
}

/**
 * Escape a value that appears INSIDE a packet line (a `#`-separated field):
 * only `&` and `$` can be escaped there. A literal `#` would unescape into
 * another field separator and a literal `%` would end the line, so neither
 * can be represented in a packet field (the validator warns about both).
 */
function escapeDemoPacketField(text) {
    return String(text)
        .replace(/&/g, '<and>')
        .replace(/\$/g, '<dollar>');
}

/**
 * Quote a script operand when it needs quoting. Within a line, spaces
 * separate parts, so any value with whitespace must be double-quoted; an
 * already-quoted value is left alone.
 */
function quoteDemoOperand(value) {
    const text = String(value);
    if (/^\s*["']/.test(text) || !/\s/.test(text)) return text;
    return `"${text}"`;
}

/** Symbolic spellings of the `if` operators; the parser also accepts the
 * words `eq ne lt le gt ge`, which the importer normalizes to these. */
const DEMO_IF_OP_ALIASES = { eq: '==', ne: '!=', lt: '<', le: '<=', gt: '>', ge: '>=' };

/* --- Generator (blocks -> script text) ---------------------------------- */

const demoGenerator = new Blockly.Generator('DemoScript');

demoGenerator.forBlock.demo_wait = function (block) {
    const ms = block.getFieldValue('MS');
    if (ms === null || ms === undefined || ms === '') return '';
    return `wait ${ms}`;
};

demoGenerator.forBlock.demo_if = function (block) {
    const a = escapeDemoText(block.getFieldValue('A') || '');
    const op = block.getFieldValue('OP') || '==';
    const b = escapeDemoText(block.getFieldValue('B') || '');
    const label = escapeDemoText(block.getFieldValue('LABEL') || '');
    return `if ${a} ${op} ${b} ${label}`;
};

demoGenerator.forBlock.demo_label = function (block) {
    const name = escapeDemoText(block.getFieldValue('NAME') || '');
    return name ? `label ${name}` : '';
};

demoGenerator.forBlock.demo_goto = function (block) {
    const name = escapeDemoText(block.getFieldValue('NAME') || '');
    return name ? `goto ${name}` : '';
};

demoGenerator.forBlock.demo_return = function () {
    return 'return';
};

demoGenerator.forBlock.demo_set = function (block) {
    const name = block.getField('VAR').getVariable().name;
    const value = quoteDemoOperand(escapeDemoText(block.getFieldValue('VALUE') || ''));
    return `set ${name} ${value}`;
};

demoGenerator.forBlock.demo_get = function (block) {
    const name = block.getField('VAR').getVariable().name;
    const path = escapeDemoText(block.getFieldValue('PATH') || '');
    return path ? `get ${name} ${path}` : '';
};

demoGenerator.forBlock.demo_concat = function (block) {
    const name = block.getField('VAR').getVariable().name;
    const value = quoteDemoOperand(escapeDemoText(block.getFieldValue('VALUE') || ''));
    const sep = block.getFieldValue('SEP');
    const sepText = (sep === null || sep === undefined || sep === '')
        ? ''
        : ` ${quoteDemoOperand(escapeDemoText(sep))}`;
    return `concat ${name} ${value}${sepText}`;
};

demoGenerator.forBlock.demo_rand = function (block) {
    const name = block.getField('VAR').getVariable().name;
    const min = escapeDemoText(block.getFieldValue('MIN') || '');
    const max = escapeDemoText(block.getFieldValue('MAX') || '');
    return `rand ${name} ${min} ${max}`;
};

demoGenerator.forBlock.demo_save = function (block) {
    const char = quoteDemoOperand(escapeDemoText(block.getFieldValue('CHAR') || ''));
    const key = escapeDemoText(block.getFieldValue('KEY') || '');
    const value = quoteDemoOperand(escapeDemoText(block.getFieldValue('VALUE') || ''));
    return `save ${char} ${key} ${value}`;
};

demoGenerator.forBlock.demo_packet = function (block) {
    const hdr = block.getFieldValue('HDR') || 'CT';
    // FIELDS holds the script-ready text between the header and the `%`
    // terminator: `#` separators are written raw and any literal `# & % $`
    // inside a field is already written as `<num>`/`<and>`/`<percent>`/
    // `<dollar>` (the importer pre-escapes each parsed arg, and the user
    // types them the same way they would in a script line).
    const fields = block.getFieldValue('FIELDS') || '';
    return `${hdr}#${fields}%`;
};

demoGenerator.forBlock.demo_packet_ct = function (block) {
    const name = escapeDemoPacketField(block.getFieldValue('NAME') || '');
    const msg = escapeDemoPacketField(block.getFieldValue('MSG') || '');
    const sfx = escapeDemoPacketField(block.getFieldValue('SFX') || '0');
    return `CT#${name}#${msg}#${sfx}%`;
};

demoGenerator.forBlock.demo_packet_mc = function (block) {
    const song = escapeDemoPacketField(block.getFieldValue('SONG') || '');
    // FieldCheckbox.getValue() returns 'TRUE'/'FALSE' strings (truthy!), so
    // a truthiness check would always emit 1 -- compare explicitly.
    const loop = (block.getFieldValue('LOOP') === true || block.getFieldValue('LOOP') === 'TRUE') ? '1' : '0';
    const fx = escapeDemoPacketField(block.getFieldValue('FX') ?? '0');
    return `MC#${song}#-1##${loop}#0#${fx}%`;
};

demoGenerator.forBlock.demo_packet_bn = function (block) {
    const bg = escapeDemoPacketField(block.getFieldValue('BG') || '');
    return `BN#${bg}%`;
};

demoGenerator.forBlock.demo_packet_ms = function (block) {
    // One field per MS arg, index-aligned with the SERVER -> CLIENT layout
    // that area.send_ic broadcasts (NOT the client -> server order that
    // aoprotocol.py's net_cmd_ms parses -- demos broadcast raw packets, so
    // clients read these fields in the server order).
    // String fields go through escapeDemoPacketField (only `&` and `$` can
    // be represented inside a packet field; `#`/`%` are warned about).
    // Checkbox fields return the strings 'TRUE'/'FALSE' from Blockly v13's
    // FieldCheckbox (booleans from older versions); the AO wire protocol
    // always uses int (0/1) for bools.
    const toWire = (v) => (
        v === true || v === 'TRUE' ? '1'
        : v === false || v === 'FALSE' ? '0'
        : v
    );
    const s = (name, dflt) => escapeDemoPacketField(String(toWire(block.getFieldValue(name) ?? dflt)));
    const n = (name, dflt) => String(toWire(block.getFieldValue(name) ?? dflt));
    return 'MS#' + [
        s('MSG_TYPE', '1'), s('PRE', ''), s('FOLDER', ''),
        s('ANIM', ''), s('TEXT', ''), s('POS', ''),
        s('SFX', ''), n('EMOTE_MOD', 0), n('CID', -1),
        n('SFX_DELAY', 0), s('BUTTON', '0'), n('EVIDENCE', -1),
        n('FLIP', 0), n('DING', 0), n('COLOR', 0),
        s('SHOWNAME', ''), s('CHARID_PAIR', '-1'), s('OTHER_FOLDER', ''),
        s('OTHER_EMOTE', ''), s('OFFSET_PAIR', '0'), s('OTHER_OFFSET', '0'),
        n('OTHER_FLIP', 0), n('NONINT_PRE', 0), s('SFX_LOOPING', '0'),
        n('SCREENSHAKE', 0), s('FRAMES_SHAKE', ''), s('FRAMES_REALIZATION', ''), s('FRAMES_SFX', ''),
        n('ADDITIVE', 0), s('EFFECT', ''), n('THIRD_CHARID', -1),
        s('THIRD_FOLDER', ''), s('THIRD_EMOTE', ''), s('THIRD_OFFSET', ''),
        n('THIRD_FLIP', 0), s('VIDEO', ''),
    ].join('#') + '%';
};

demoGenerator.forBlock.demo_packet_hp = function (block) {
    const side = block.getFieldValue('SIDE') || '1';
    const val = String(block.getFieldValue('VAL') ?? 0);
    return `HP#${side}#${val}%`;
};

demoGenerator.forBlock.demo_packet_rt = function (block) {
    const type = block.getFieldValue('TYPE') || 'testimony1';
    const arg = (block.getFieldValue('ARG') || '').trim();
    // No trailing `#` when the optional arg is blank: the parser strips a
    // `#` before `%`, so `RT#x#%` and `RT#x%` are the same packet -- emit
    // the clean form.
    return arg ? `RT#${type}#${escapeDemoPacketField(arg)}%` : `RT#${type}%`;
};

demoGenerator.forBlock.demo_packet_jd = function (block) {
    const mode = block.getFieldValue('MODE') || '1';
    return `JD#${mode}%`;
};

demoGenerator.forBlock.demo_command = function (block) {
    const cmd = escapeDemoText(block.getFieldValue('CMD') || '');
    return cmd ? `/${cmd}%` : '';
};

/**
 * Chain statements together: each block's code is one script line, and the
 * next block in the stack follows on its own line. Blockly's base generator
 * does not follow `next` connections (language generators override this) --
 * without this override workspaceToCode would only emit the first block.
 */
demoGenerator.scrub_ = function (block, code, thisOnly) {
    const nextBlock = block.getNextBlock();
    const nextCode = (thisOnly || !nextBlock) ? '' : this.blockToCode(nextBlock);
    return (code ? `${code}\n` : '') + nextCode;
};

/** Generate the script text for a workspace (blocks -> text). */
function demoWorkspaceToText(workspace) {
    return demoGenerator.workspaceToCode(workspace);
}

/* --- Validation (client-side warnings) ---------------------------------- */

/**
 * Client-side checks over the workspace, mirroring what would go wrong at
 * runtime. These are convenience warnings only -- the server is the final
 * authority. Returns an array of warning strings (empty when clean).
 */
function demoValidateWorkspace(workspace) {
    const warnings = [];
    const blocks = workspace.getAllBlocks(false);
    const labels = new Set();
    blocks.forEach((b) => {
        if (b.type === 'demo_label') {
            const name = (b.getFieldValue('NAME') || '').trim();
            if (name) labels.add(name);
        }
    });
    const missing = (b, field, what) => {
        if (!String(b.getFieldValue(field) || '').trim()) warnings.push(what);
    };
    const fieldHas = (b, field, ch) => String(b.getFieldValue(field) || '').includes(ch);
    blocks.forEach((b) => {
        // A literal `%` cannot survive in script text: the parser unescapes
        // `<percent>` to `%` before splitting lines, so the line would end
        // early (docs/demo_scripting.md's escape table notwithstanding).
        // Every other field type is checked; only string-valued fields can
        // carry one.
        b.inputList.forEach((input) => {
            input.fieldRow.forEach((f) => {
                let v = null;
                try { v = f.getValue && f.getValue(); } catch (e) { v = null; }
                if (typeof v === 'string' && v.includes('%')) {
                    warnings.push(`The script language can't represent a literal "%" in text (the line would end there); remove it from a field of a "${b.type}" block.`);
                }
            });
        });
        switch (b.type) {
            case 'demo_if': {
                const label = (b.getFieldValue('LABEL') || '').trim();
                if (!label) warnings.push('An "if" block is missing its jump-to label.');
                else if (!labels.has(label)) warnings.push(`"if" jumps to undefined label "${label}".`);
                missing(b, 'A', 'An "if" block is missing its left value.');
                missing(b, 'B', 'An "if" block is missing its right value.');
                break;
            }
            case 'demo_goto': {
                const label = (b.getFieldValue('NAME') || '').trim();
                if (!label) warnings.push('A "goto" block is missing its label.');
                else if (!labels.has(label)) warnings.push(`"goto" jumps to undefined label "${label}".`);
                break;
            }
            case 'demo_label':
                missing(b, 'NAME', 'A "label" block needs a name.');
                break;
            case 'demo_set':
                missing(b, 'VALUE', 'A "set" block is missing its value.');
                break;
            case 'demo_get':
                missing(b, 'PATH', 'A "get" block is missing its path (e.g. clients.count).');
                break;
            case 'demo_concat':
                missing(b, 'VALUE', 'A "concat" block is missing its value.');
                break;
            case 'demo_save': {
                const char = String(b.getFieldValue('CHAR') || '').trim();
                missing(b, 'KEY', 'A "save" block is missing its key.');
                missing(b, 'VALUE', 'A "save" block is missing its value.');
                if (char && !/^["']/.test(char) && !/^-?\d+$/.test(char)) {
                    warnings.push(`"save" character "${char}" should be an id number or a quoted folder name like "Phoenix".`);
                }
                break;
            }
            case 'demo_packet':
                // FIELDS is script-ready text: `#` separators are expected, so
                // only the generic `%` check above applies here.
                missing(b, 'FIELDS', 'A packet block is missing its fields (the part after the header).');
                break;
            case 'demo_packet_ct':
                missing(b, 'MSG', 'A CT message block is missing its message.');
                if (fieldHas(b, 'NAME', '#') || fieldHas(b, 'MSG', '#') || fieldHas(b, 'SFX', '#')) {
                    warnings.push('A CT message field contains "#" -- a "#" inside a packet field splits it into extra fields, so it can\'t be sent literally.');
                }
                break;
            case 'demo_packet_mc':
                missing(b, 'SONG', 'A music block is missing its song name.');
                if (fieldHas(b, 'SONG', '#') || fieldHas(b, 'FX', '#')) {
                    warnings.push('A music field contains "#" -- a "#" inside a packet field splits it into extra fields, so it can\'t be sent literally.');
                }
                break;
            case 'demo_packet_bn':
                missing(b, 'BG', 'A background block is missing the background name.');
                if (fieldHas(b, 'BG', '#')) {
                    warnings.push('A background name contains "#" -- a "#" inside a packet field splits it into extra fields, so it can\'t be sent literally.');
                }
                break;
            case 'demo_packet_ms': {
                // Wire values the server always fills on broadcast (msg_type,
                // charid_pair, offset_pair, sfx_looping) -- mirrors the
                // client parser's "requires at least 1 character" STR rule.
                // The remaining fields (folder/pos/sfx/frames_*/effect,
                // other_*, third_*) are legitimately blank for narration or
                // when no one is paired in the demo runtime.
                ['MSG_TYPE', 'CHARID_PAIR', 'OFFSET_PAIR', 'SFX_LOOPING'].forEach((fld) => {
                    missing(b, fld, `The MS field "${fld.toLowerCase()}" requires at least 1 character (STR).`);
                });
                missing(b, 'BUTTON', 'The MS field "button" needs a value (0 for none).');
                const badHash = ['MSG_TYPE', 'PRE', 'FOLDER', 'ANIM', 'TEXT', 'POS', 'SFX', 'SHOWNAME', 'CHARID_PAIR', 'OTHER_FOLDER', 'OTHER_EMOTE', 'OFFSET_PAIR', 'OTHER_OFFSET', 'SFX_LOOPING', 'FRAMES_SHAKE', 'FRAMES_REALIZATION', 'FRAMES_SFX', 'EFFECT', 'THIRD_FOLDER', 'THIRD_EMOTE', 'THIRD_OFFSET', 'VIDEO', 'BUTTON']
                    .filter((fld) => fieldHas(b, fld, '#'));
                if (badHash.length) {
                    warnings.push('An MS field contains "#" -- a "#" inside a packet field splits it into extra fields, so it can\'t be sent literally.');
                }
                break;
            }
            case 'demo_packet_rt':
                if (fieldHas(b, 'ARG', '#')) {
                    warnings.push('The RT extra value contains "#" -- a "#" inside a packet field splits it into extra fields, so it can\'t be sent literally.');
                }
                break;
            case 'demo_command':
                missing(b, 'CMD', 'A command block is missing the command (e.g. "timer 1 5m start").');
                break;
            default:
                break;
        }
    });
    return warnings;
}

/* --- Importer (script text -> blocks) ----------------------------------- */

/**
 * Build a Blockly serialization-workspace state from the server's parsed
 * instruction tuples (see parse_demo_description). Variable fields must
 * reference variables by id with a top-level `variables` array (verified
 * against Blockly v13.2.1), so variable targets are pre-scanned and given
 * stable ids before the block states are built.
 */
function demoInstructionsToWorkspaceState(instructions) {
    const variables = [];
    const varIds = new Map();
    const varIdFor = (name) => {
        if (!varIds.has(name)) {
            const id = `gmvar_${variables.length}`;
            varIds.set(name, id);
            variables.push({ name, id });
        }
        return varIds.get(name);
    };

    let first = null;
    let prev = null;
    const push = (block) => {
        if (!first) first = block;
        else prev.next = { block };
        prev = block;
    };

    (instructions || []).forEach((raw) => {
        const kind = raw[0];
        const rest = raw.slice(1);
        let block = null;
        switch (kind) {
            case 'wait':
                block = { type: 'demo_wait', fields: { MS: Math.round(Number(rest[0]) * 1000) || 0 } };
                break;
            case 'packet': {
                const hdr = rest[0];
                const args = rest[1] || [];
                if (hdr === 'CT' && args.length === 3) {
                    block = {
                        type: 'demo_packet_ct',
                        fields: { NAME: args[0], MSG: args[1], SFX: args[2] },
                    };
                } else if (hdr === 'MC' && args.length === 6 && args[1] === '-1' && args[2] === '' && args[4] === '0') {
                    block = {
                        type: 'demo_packet_mc',
                        fields: { SONG: args[0], LOOP: String(args[3]) === '1', FX: Number(args[5]) || 0 },
                    };
                } else if (hdr === 'BN' && args.length === 1) {
                    block = { type: 'demo_packet_bn', fields: { BG: args[0] } };
                } else if (hdr === 'MS' && args.length <= 36) {
                    // Every MS packet maps onto the structured MS block,
                    // however many fields the script has: hand-written scripts
                    // send shorter layouts, which are just the same fields
                    // with trailing blanks missing. The positional mapping
                    // below fills missing slots with the same defaults the
                    // generator emits (e.g. 35 args = the full packet with an
                    // empty trailing `video` field, since the parser drops a
                    // `#` before `%`). Over-long MS packets (> 36 args) still
                    // fall through to the generic packet block instead, so no
                    // fields are ever dropped.
                    const a = (i, dflt) => (i < args.length ? args[i] : dflt);
                    const num = (i, dflt) => {
                        const v = Number(a(i, dflt));
                        return Number.isFinite(v) ? v : dflt;
                    };
                    // Dropdown fields store string option values and Blockly's
                    // setValue matches them with strict equality, so a numeric
                    // value (or one outside the option list, from a
                    // hand-written script) would throw "unavailable option"
                    // and kill the whole import. Coerce to a valid option,
                    // falling back to the default.
                    const dropdown = (i, dflt, options) => {
                        const v = a(i, dflt);
                        return options.includes(v) ? v : dflt;
                    };
                    // Checkbox fields must load as booleans: Blockly v13's
                    // FieldCheckbox only validates true/false and
                    // 'TRUE'/'FALSE', so a numeric 0/1 would be rejected and
                    // the default silently kept -- a script with flip=1
                    // would import with the flag cleared.
                    const flag = (i, dflt) => {
                        const v = a(i, dflt);
                        return v === true || v === 'TRUE' || String(v).toLowerCase() === 'true' || String(v) === '1';
                    };
                    block = {
                        type: 'demo_packet_ms',
                        fields: {
                            MSG_TYPE: dropdown(0, '1', ['0', '1', '2', '3', '4', '5']), PRE: a(1, ''), FOLDER: a(2, ''),
                            ANIM: a(3, ''), TEXT: a(4, ''), POS: a(5, ''),
                            SFX: a(6, ''), EMOTE_MOD: dropdown(7, '0', ['0', '1', '5', '6']), CID: num(8, -1),
                            SFX_DELAY: num(9, 0), BUTTON: a(10, '0'), EVIDENCE: num(11, -1),
                            FLIP: flag(12, false), DING: flag(13, false), COLOR: num(14, 0),
                            SHOWNAME: a(15, ''), CHARID_PAIR: a(16, '-1'), OTHER_FOLDER: a(17, ''),
                            OTHER_EMOTE: a(18, ''), OFFSET_PAIR: a(19, '0'), OTHER_OFFSET: a(20, '0'),
                            OTHER_FLIP: flag(21, false), NONINT_PRE: flag(22, false), SFX_LOOPING: flag(23, false),
                            SCREENSHAKE: flag(24, false), FRAMES_SHAKE: a(25, ''), FRAMES_REALIZATION: a(26, ''), FRAMES_SFX: a(27, ''),
                            ADDITIVE: flag(28, false), EFFECT: a(29, ''), THIRD_CHARID: num(30, -1),
                            THIRD_FOLDER: a(31, ''), THIRD_EMOTE: a(32, ''), THIRD_OFFSET: a(33, ''),
                            THIRD_FLIP: flag(34, false), VIDEO: a(35, ''),
                        },
                    };
                } else if (
                    hdr === 'HP' && args.length === 2
                    && (args[0] === '1' || args[0] === '2')
                    && /^-?\d+$/.test(args[1])
                ) {
                    block = {
                        type: 'demo_packet_hp',
                        fields: { SIDE: args[0], VAL: Number(args[1]) },
                    };
                } else if (hdr === 'RT' && (args.length === 1 || args.length === 2)) {
                    // TYPE is a free-text field, so every RT packet maps to
                    // the shortcut block -- custom animation names included.
                    block = {
                        type: 'demo_packet_rt',
                        fields: { TYPE: args[0], ARG: args[1] !== undefined ? args[1] : '' },
                    };
                } else if (hdr === 'JD' && args.length === 1 && ['-1', '0', '1'].includes(args[0])) {
                    block = { type: 'demo_packet_jd', fields: { MODE: args[0] } };
                } else {
                    block = {
                        type: 'demo_packet',
                        // Each parsed arg is already unescaped, so re-escape it
                        // before joining with `#` (see demo_packet generator).
                        fields: { HDR: hdr, FIELDS: args.map(escapeDemoPacketField).join('#') },
                    };
                }
                break;
            }
            case 'command': {
                // Map onto the per-arg block when the command is in the
                // catalog and the tokens fit its spec; otherwise fall back to
                // the free-form command block (aliases, mod-only commands,
                // unparseable leftovers all land there).
                const cmd = String(rest[0] || '').toLowerCase();
                const arg = rest[1] || '';
                const meta = DEMO_COMMAND_CATALOG.find((c) => c.name === cmd);
                block = mapDemoCommandToBlock(meta, cmd, arg);
                break;
            }
            case 'set':
            case 'get':
                block = {
                    type: kind === 'set' ? 'demo_set' : 'demo_get',
                    fields: {
                        VAR: { id: varIdFor(String(rest[0])) },
                        [kind === 'set' ? 'VALUE' : 'PATH']: rest[1] !== undefined ? rest[1] : '',
                    },
                };
                break;
            case 'concat':
                block = {
                    type: 'demo_concat',
                    fields: {
                        VAR: { id: varIdFor(String(rest[0])) },
                        VALUE: rest[1] !== undefined ? rest[1] : '',
                        SEP: rest[2] !== undefined ? rest[2] : '',
                    },
                };
                break;
            case 'rand':
                block = {
                    type: 'demo_rand',
                    fields: {
                        VAR: { id: varIdFor(String(rest[0])) },
                        MIN: rest[1] !== undefined ? rest[1] : '',
                        MAX: rest[2] !== undefined ? rest[2] : '',
                    },
                };
                break;
            case 'save':
                block = {
                    type: 'demo_save',
                    fields: {
                        CHAR: rest[0] !== undefined ? rest[0] : '',
                        KEY: rest[1] !== undefined ? rest[1] : '',
                        VALUE: rest[2] !== undefined ? rest[2] : '',
                    },
                };
                break;
            case 'if':
                block = {
                    type: 'demo_if',
                    fields: {
                        A: rest[0] !== undefined ? rest[0] : '',
                        OP: DEMO_IF_OP_ALIASES[rest[1]] || rest[1] || '==',
                        B: rest[2] !== undefined ? rest[2] : '',
                        LABEL: rest[3] !== undefined ? rest[3] : '',
                    },
                };
                break;
            case 'label':
                block = { type: 'demo_label', fields: { NAME: rest[0] !== undefined ? rest[0] : '' } };
                break;
            case 'goto':
                block = { type: 'demo_goto', fields: { NAME: rest[0] !== undefined ? rest[0] : '' } };
                break;
            case 'return':
                block = { type: 'demo_return' };
                break;
            default:
                // Unknown instruction kinds are never produced by the server
                // parser; skipping keeps the workspace clean rather than
                // crashing on a foreign tuple.
                break;
        }
        if (block) push(block);
    });

    return {
        variables,
        blocks: { languageVersion: 0, blocks: first ? [first] : [] },
    };
}

/* --- DemoBlockEditor ---------------------------------------------------- */

/**
 * Owns one Blockly workspace inside a container element. The editor is
 * purely a view over a script-text buffer: the tab hands it parsed
 * instructions to import (text -> blocks), and it reports the generated
 * script text + warnings on every workspace change (blocks -> text).
 */
class DemoBlockEditor {
    /**
     * @param {HTMLElement} container - element Blockly injects into.
     * @param {Function} onChange - (scriptText, warnings) called after the
     *   workspace is created/imported and on every edit.
     */
    constructor(container, onChange) {
        this._container = container;
        this._onChange = onChange;
        this._workspace = null;
        this._loading = false;
    }

    /** Create the workspace on first use (lazy: Blockly is only initialized
     * the first time the Visual sub-tab is opened). */
    ensure() {
        if (this._workspace) return;
        this._workspace = Blockly.inject(this._container, {
            toolbox: DEMO_TOOLBOX,
            theme: Blockly.Themes.Dark,
            trashcan: true,
            zoom: { controls: true, wheel: true, startScale: 0.85, maxScale: 1.5, minScale: 0.35 },
            move: { scrollbars: true, drag: true, wheel: true },
            grid: { spacing: 24, length: 3, colour: '#2a2f42', snap: true },
        });
        // Wire the toolbox's "Create variable…" button. Flyout buttons look
        // their callback up on the button's *target workspace* when clicked
        // (FlyoutButton.onMouseUp -> targetWorkspace.getButtonCallback) and
        // invoke it with the button itself, so the callback must be
        // registered on this workspace -- the toolbox's own callback map is
        // never consulted and registering there makes the button silently do
        // nothing. createVariableButtonHandler then expects the *workspace*
        // as its argument (it calls workspace.getVariableMap()/getFlyout()
        // directly); passing the button leaves it with a TypeError after the
        // dialog closes and no variable is created. Blockly's own variables
        // category wires it the same way: handler(button.getTargetWorkspace()).
        if (typeof this._workspace.registerButtonCallback === 'function') {
            this._workspace.registerButtonCallback('CREATE_VARIABLE', (button) => {
                Blockly.Variables.createVariableButtonHandler(button.getTargetWorkspace());
            });
        }
        // Prime the Variables category with the current variables (a script
        // whose set/get blocks reference variables gets a chip per variable
        // right away), then keep it in step whenever the variable map
        // changes: creating a variable immediately puts a set/get pair for
        // it in the flyout, like Blockly's own category. The Commands
        // category gets the server's command catalog the same way (the
        // static toolbox only carries the free-form fallback until the
        // catalog lands).
        demoRefreshVariablesFlyout(this._workspace);
        demoRefreshGetInsertOptions(this._workspace);
        demoRefreshCommandsToolbox(this._workspace);
        this._workspace.addChangeListener((event) => {
            // Skip UI-only events (selection, clicks) and events fired while
            // we are programmatically loading a script.
            if (this._loading || !event || event.isUiEvent) return;
            // Creating, renaming or deleting a variable changes what the
            // Variables flyout should offer; refresh that one category (and
            // the get blocks' insert dropdown, which lists the variables).
            if (event.type === 'var_create' || event.type === 'var_rename' || event.type === 'var_delete') {
                demoRefreshVariablesFlyout(this._workspace);
                demoRefreshGetInsertOptions(this._workspace);
            } else if (event.type === 'create') {
                // Blocks dragged in from the toolbox need the workspace's
                // variables in their insert dropdown. setOptions is cheap
                // (no flyout rebuild), so refresh on every block create.
                demoRefreshGetInsertOptions(this._workspace);
            }
            if (event.type === 'change') {
                if (event.name === 'INSERT_VAR' && event.newValue) {
                    // "Insert variable…" picked: replace the PATH field
                    // with the chosen path or variable name, then reset
                    // the dropdown to its placeholder.
                    const block = this._workspace.getBlockById(event.blockId);
                    if (block && block.type === 'demo_get') {
                        this._setPath(block, event.newValue);
                        const dropdown = block.getField('INSERT_VAR');
                        if (dropdown) dropdown.setValue('');
                    }
                }
            }
            this._emit();
        });
        this._emit();
    }

    /** True once the workspace exists (i.e. the Visual sub-tab was opened). */
    get ready() {
        return this._workspace !== null;
    }

    /** Current script text generated from the blocks. */
    get text() {
        if (!this._workspace) return '';
        return demoWorkspaceToText(this._workspace);
    }

    /** Current client-side warnings over the blocks. */
    get warnings() {
        if (!this._workspace) return [];
        return demoValidateWorkspace(this._workspace);
    }

    /** Replace the workspace contents with parsed instructions. */
    importInstructions(instructions) {
        this.ensure();
        this._loading = true;
        try {
            this._workspace.clear();
            Blockly.serialization.workspaces.load(
                demoInstructionsToWorkspaceState(instructions),
                this._workspace,
            );
        } finally {
            this._loading = false;
        }
        // Loading (or clearing) can change the variable set without firing
        // variable events, so resync the flyout and the get insert dropdown.
        demoRefreshVariablesFlyout(this._workspace);
        demoRefreshGetInsertOptions(this._workspace);
        this._emit();
    }

    /**
     * Replace a get block's PATH field with the picked path or variable
     * name. The dropdown's "insert" action swaps the whole value rather
     * than appending, so a chosen live path can't get silently glued onto
     * stale text already in the field.
     */
    _setPath(block, name) {
        block.getField('PATH').setValue(String(name));
    }

    /**
     * Replace the get blocks' curated live-path dropdown menu with the
     * server-generated list (GET /api/gm/demos/paths -> scripting.py
     * `live_path_menu`), updating any get blocks already in the workspace.
     * Safe to call before the workspace exists: the options apply when the
     * first get block appears. The built-in fallback list stays in force
     * until this is called.
     */
    setInsertPathOptions(paths) {
        demoSetInsertPathOptions(this._workspace, paths);
    }

    /**
     * Populate the Commands toolbox category with one block per command the
     * demo may run (GET /api/gm/demos/commands -> server/scripting.py's
     * CommandLister). Safe to call before the workspace exists: the block
     * definitions are registered and applied when the workspace is created.
     */
    setCommandCatalog(commands) {
        demoSetCommandCatalog(this._workspace, commands);
    }

    /** Clear the workspace (new script). */
    clear() {
        if (!this._workspace) return;
        this._loading = true;
        try {
            this._workspace.clear();
        } finally {
            this._loading = false;
        }
        demoRefreshVariablesFlyout(this._workspace);
        demoRefreshGetInsertOptions(this._workspace);
        this._emit();
    }

    _emit() {
        if (this._onChange) {
            this._onChange(this.text, this.warnings);
        }
    }
}
