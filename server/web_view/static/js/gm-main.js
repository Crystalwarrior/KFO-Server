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

        shell.registerTab('areas', new AreasGraphTab(shell, api, document.getElementById('tab-areas')));
        shell.registerTab('clients', new ClientsTab(shell, api, document.getElementById('tab-clients')));
        shell.registerTab('characters', new CharactersTab(shell, api, document.getElementById('tab-characters')));
        shell.registerTab('commands', new CommandsTab(shell, api, document.getElementById('tab-commands')));
        shell.registerTab('demos', new DemosTab(shell, api, document.getElementById('tab-demos')));

        shell.start();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
