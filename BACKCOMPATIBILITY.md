# COMPATIBILITY NOTICES

This document is to document backwards-incompatible changes that are being introduced to newer versions of TsuserverDR. All listed items affect developers. Special tags to some items will be added as follows: Items marked with [O] affect server operators, items marked with [P] affect players.
TsuserverDR follows a variation of semantic revisioning, where for a public version number `X.Y.Z` or `X.Y.Z-postW`, backwards-incompatible changes for functionality...

* Will not be introduced if W increases. These are post-releases.
* May be announced and either console/client warnings may be sent if Z increases. These are minor releases.
* May be introduced if Y increases, only if previously announced in a minor release. These are major releases.
* Are definitely introduced if X increases. These are primary releases.

For tests, backwards-incompatible changes to existing test files may be introduced at any time to comply with whatever patches are being made or new features are being introduced. Modifications to test files will not be included in this document.

For development versions, marked with `-a`, `-b` and `-RC`, backwards-incompatible will be rapidly introduced and not typically announced. Such notices will not be included in this document. Server operators should avoid using development versions in their server unless they know what they are doing. 

## 4.2.1
* [P] Deprecation warnings are now sent (but functionality still remains) if players attempt to use any of the following commands:
- **allow_iniswap**: Same as /can_iniswap.
- **delete_areareachlock**: Same as /passage_clear.
- **mutepm**: Same as /toggle_pm.
- **restore_areareachlock**: Same as /passage_restore.
- **showname_list**: Same as /showname_areas.
- **toggleglobal**: Same as /toggle_global.
- **toggle_areareachlock**: Same as /can_passagelock.
- **toggle_rollp**: Same as /can_rollp.
- **toggle_rpgetarea**: Same as /can_rpgetarea.
- **toggle_rpgetareas**: Same as /can_rpgetareas.
* [O] `logs/server.log` will now go unused as server logging information will be split into monthly files in the format `logs/server-[YEAR]-[MONTH].log`. 
* Deprecation warnings are now sent for uses of the optional parameter `ic_params` (a list of IC argument values) in ClientManager.Client.send_ic and ClientManager.Client.send_ic_others. The recommended parameter is now `params` (a dictionary matching argumet names to their values).
* Deprecation warnings are now sent for uses of the instance field `TsuserverDR.music_list_ao2`. The recommended alternative is to obtain the return value of the method `TsuserverDR.build_music_list_ao2()` instead (whose return value has changed from None to list of str)
* 'cccc_ic_support' is now an additional argument sent to clients as part of a server response via an 'FL' packet