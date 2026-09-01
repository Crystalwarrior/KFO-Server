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
        // Full AO 2.8 IC message (MS) packet, field-for-field with the
        // server's spec in aoprotocol.py (the "KFO Client validation
        // monstrosity" layout). Arg types follow that spec: STR fields
        // require at least 1 character, STR_OR_EMPTY fields may be blank.
        // folder/pos/sfx/frames_*/effect are STR in the spec but the demo
        // runtime legitimately sends them empty (narration; a blank pos even
        // inherits the area's last IC message position), so only the STR
        // fields the server itself never sends empty are validated below.
        type: 'demo_packet_ms',
        message0: 'MS (IC message)',
        message1: 'msg_type %1   pre %2   folder %3',
        message2: 'anim %1   text %2   pos %3',
        message3: 'sfx %1   emote_mod %2   cid %3',
        message4: 'sfx_delay %1   button %2   evidence %3',
        message5: 'flip %1   ding %2   color %3',
        message6: 'showname %1   charid_pair %2   offset_pair %3',
        message7: 'nonint_pre %1   sfx_looping %2   screenshake %3',
        message8: 'frames_shake %1   frames_realization %2   frames_sfx %3',
        message9: 'additive %1   effect %2   third_charid %3   video %4',
        args1: [
            { type: 'field_input', name: 'MSG_TYPE', text: '1' },
            { type: 'field_input', name: 'PRE', text: '' },
            { type: 'field_input', name: 'FOLDER', text: '' },
        ],
        args2: [
            { type: 'field_input', name: 'ANIM', text: '' },
            // field_multilinetext: multi-line IC text (Message 2 is the
            // "text" argument of the MS packet). Enter commits, Shift+Enter
            // inserts a newline.
            { type: 'field_multilinetext', name: 'TEXT', text: '' },
            { type: 'field_input', name: 'POS', text: '' },
        ],
        args3: [
            { type: 'field_input', name: 'SFX', text: '' },
            { type: 'field_number', name: 'EMOTE_MOD', value: 0 },
            { type: 'field_number', name: 'CID', value: -1 },
        ],
        args4: [
            { type: 'field_number', name: 'SFX_DELAY', value: 0 },
            { type: 'field_input', name: 'BUTTON', text: '0' },
            { type: 'field_number', name: 'EVIDENCE', value: -1 },
        ],
        args5: [
            { type: 'field_number', name: 'FLIP', value: 0 },
            { type: 'field_number', name: 'DING', value: 0 },
            { type: 'field_number', name: 'COLOR', value: 0 },
        ],
        args6: [
            { type: 'field_input', name: 'SHOWNAME', text: '' },
            { type: 'field_input', name: 'CHARID_PAIR', text: '-1' },
            { type: 'field_input', name: 'OFFSET_PAIR', text: '0' },
        ],
        args7: [
            { type: 'field_number', name: 'NONINT_PRE', value: 0 },
            { type: 'field_input', name: 'SFX_LOOPING', text: '0' },
            { type: 'field_number', name: 'SCREENSHAKE', value: 0 },
        ],
        args8: [
            { type: 'field_input', name: 'FRAMES_SHAKE', text: '' },
            { type: 'field_input', name: 'FRAMES_REALIZATION', text: '' },
            { type: 'field_input', name: 'FRAMES_SFX', text: '' },
        ],
        args9: [
            { type: 'field_number', name: 'ADDITIVE', value: 0 },
            { type: 'field_input', name: 'EFFECT', text: '' },
            { type: 'field_number', name: 'THIRD_CHARID', value: -1 },
            { type: 'field_input', name: 'VIDEO', text: '' },
        ],
        previousStatement: null,
        nextStatement: null,
        colour: 20,
        tooltip: 'Broadcast an IC (MS) message with all AO 2.8 fields. STR fields need at least 1 character; STR_OR_EMPTY fields (pre, anim, text, showname, video) may be blank. Leave pos blank for narration -- the demo runner reuses the area\'s last IC message position. Use <!var> inside text/showname to drop in a variable.',
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
    const loop = block.getFieldValue('LOOP') ? '1' : '0';
    const fx = escapeDemoPacketField(block.getFieldValue('FX') ?? '0');
    return `MC#${song}#-1##${loop}#0#${fx}%`;
};

demoGenerator.forBlock.demo_packet_bn = function (block) {
    const bg = escapeDemoPacketField(block.getFieldValue('BG') || '');
    return `BN#${bg}%`;
};

demoGenerator.forBlock.demo_packet_ms = function (block) {
    // One field per MS arg, index-aligned with aoprotocol.py's 28-arg spec.
    // String fields go through escapeDemoPacketField (only `&` and `$` can
    // be represented inside a packet field; `#`/`%` are warned about).
    const s = (name, dflt) => escapeDemoPacketField(String(block.getFieldValue(name) ?? dflt));
    const n = (name, dflt) => String(block.getFieldValue(name) ?? dflt);
    return 'MS#' + [
        s('MSG_TYPE', '1'), s('PRE', ''), s('FOLDER', ''),
        s('ANIM', ''), s('TEXT', ''), s('POS', ''),
        s('SFX', ''), n('EMOTE_MOD', 0), n('CID', -1),
        n('SFX_DELAY', 0), s('BUTTON', '0'), n('EVIDENCE', -1),
        n('FLIP', 0), n('DING', 0), n('COLOR', 0),
        s('SHOWNAME', ''), s('CHARID_PAIR', '-1'), s('OFFSET_PAIR', '0'),
        n('NONINT_PRE', 0), s('SFX_LOOPING', '0'), n('SCREENSHAKE', 0),
        s('FRAMES_SHAKE', ''), s('FRAMES_REALIZATION', ''), s('FRAMES_SFX', ''),
        n('ADDITIVE', 0), s('EFFECT', ''), n('THIRD_CHARID', -1),
        s('VIDEO', ''),
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
                // STR fields the server itself never sends empty: the spec's
                // "requires at least 1 character" rule (aoprotocol.py). The
                // remaining STR fields (folder/pos/sfx/frames_*/effect) are
                // legitimately blank for narration in the demo runtime.
                ['MSG_TYPE', 'CHARID_PAIR', 'OFFSET_PAIR', 'SFX_LOOPING'].forEach((fld) => {
                    missing(b, fld, `The MS field "${fld.toLowerCase()}" requires at least 1 character (STR).`);
                });
                missing(b, 'BUTTON', 'The MS field "button" needs a value (0 for none).');
                const badHash = ['MSG_TYPE', 'PRE', 'FOLDER', 'ANIM', 'TEXT', 'POS', 'SFX', 'SHOWNAME', 'CHARID_PAIR', 'OFFSET_PAIR', 'SFX_LOOPING', 'FRAMES_SHAKE', 'FRAMES_REALIZATION', 'FRAMES_SFX', 'EFFECT', 'VIDEO', 'BUTTON']
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
                } else if (hdr === 'MS' && args.length <= 28) {
                    // Every MS packet maps onto the structured MS block,
                    // however many fields the script has: older AO clients and
                    // hand-written scripts send shorter layouts, which are just
                    // the same fields with trailing blanks missing. The
                    // positional mapping below fills missing slots with the
                    // same defaults the generator emits (e.g. 27 args = the
                    // full packet with an empty trailing `video` field, since
                    // the parser drops a `#` before `%`). Over-long MS packets
                    // (> 28 args) still fall through to the generic packet
                    // block instead, so no fields are ever dropped.
                    const a = (i, dflt) => (i < args.length ? args[i] : dflt);
                    const num = (i, dflt) => {
                        const v = Number(a(i, dflt));
                        return Number.isFinite(v) ? v : dflt;
                    };
                    block = {
                        type: 'demo_packet_ms',
                        fields: {
                            MSG_TYPE: a(0, '1'), PRE: a(1, ''), FOLDER: a(2, ''),
                            ANIM: a(3, ''), TEXT: a(4, ''), POS: a(5, ''),
                            SFX: a(6, ''), EMOTE_MOD: num(7, 0), CID: num(8, -1),
                            SFX_DELAY: num(9, 0), BUTTON: a(10, '0'), EVIDENCE: num(11, -1),
                            FLIP: num(12, 0), DING: num(13, 0), COLOR: num(14, 0),
                            SHOWNAME: a(15, ''), CHARID_PAIR: a(16, '-1'), OFFSET_PAIR: a(17, '0'),
                            NONINT_PRE: num(18, 0), SFX_LOOPING: a(19, '0'), SCREENSHAKE: num(20, 0),
                            FRAMES_SHAKE: a(21, ''), FRAMES_REALIZATION: a(22, ''), FRAMES_SFX: a(23, ''),
                            ADDITIVE: num(24, 0), EFFECT: a(25, ''), THIRD_CHARID: num(26, -1),
                            VIDEO: a(27, ''),
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
                const cmd = rest[0];
                const arg = rest[1] || '';
                block = { type: 'demo_command', fields: { CMD: arg ? `${cmd} ${arg}` : cmd } };
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
        // it in the flyout, like Blockly's own category.
        demoRefreshVariablesFlyout(this._workspace);
        demoRefreshGetInsertOptions(this._workspace);
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
