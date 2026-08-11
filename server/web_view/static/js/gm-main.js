/**
 * gm-main.js
 * Bootstrap: wires an ApiClient, a GMPanelShell, and one instance of
 * each tab class together, then starts the shell. This is the only
 * file that constructs the object graph -- everything else receives
 * its collaborators via constructor injection.
 */

(function () {
    function boot() {
        const api = new ApiClient();
        const shell = new GMPanelShell(api, document.body);

        shell.registerTab('areas', new AreasGraphTab(shell, api, document.getElementById('tab-areas'), shell.localContent));
        shell.registerTab('clients', new ClientsTab(shell, api, document.getElementById('tab-clients'), shell.localContent));
        shell.registerTab('characters', new CharactersTab(shell, api, document.getElementById('tab-characters'), shell.localContent));
        shell.registerTab('commands', new CommandsTab(shell, api, document.getElementById('tab-commands')));
        shell.registerTab('evidence', new EvidenceTab(shell, api, document.getElementById('tab-evidence'), shell.localContent));
        shell.registerTab('data', new GMDataTab(shell, api, document.getElementById('tab-data')));

        shell.start();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
