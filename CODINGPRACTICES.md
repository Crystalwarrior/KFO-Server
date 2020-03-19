# CONTRIBUTION GUIDELINES

This document will present best coding practices and contribution standards collaborators are expected to follow if they wish to contribute to TsuserverDR. Note this applies exclusively to contributions to `Chrezm/TsuserverDR`, forks from this repository may decide to also use these guidelines, modify them as they need, or not have any guidelines at all. Please also read `BACKCOMPATIBILITY.md` for further instructions regarding maintaining backwards compatibility in this project.

## Best pull request practices
* Pull requests should have meaningful descriptions of what they include and be addressed to the following repositories as follows:
  - `master` will only take pull requests that either include critical bugfixes or are merge requests of approved release candidates.
  - `4.x.y-dev` will take pull requests that introduce new features, fix bugs in development versions or earlier, etc.
* Follow the instructions in `BACKCOMPATIBILITY.md` to determine what sort of changes will be accepted for what sort of release. Changes that do not follow proper backwards compatibility practices may be rejected.
* Pull requests should include code that passes *all* tests in `test.py`. If there is a particular reason you feel the tests themselves are broken, let the repository manager know in your pull request or privately. Do not modify existing tests without permission, but you are free to add more tests otherwise (either to existing files or in new ones).
* Pull requests will be run against a code coverage tool to determine how well new contributions are tested with `test.py`. Features that are very poorly tested by `test.py` code may be subject to further manual review. In general, for each new feature, try to add tests that can test your feature automatically.
* The repository manager may initiate a code review of the pull request via the Github review system. All review comments must be addressed either in the form of a code change or a comment explaining why you do not believe a code change is required before the pull request is approved.
* Pull request commits should include short but meaningful commit messages (at most 100 characters). If you want to elaborate on your commit messages, make a multiline commit messages, but keep all lines in there to at most 100 characters.
* If any of your commits address an existing issue in the project's Github Issues page, include the issue number in the commit message preceded by # (so if you start work on issue 48, include `#48` in the first line of your commit message).

## Best coding practices for Python code
* All code shall be backwards compatible up to the earliest version of Python explicitly supported in README.md. If your contribution absolutely requires a later version of Python, talk to the repository manager.
* Only libraries from a standard Python installation (which is available in all Python versions supported by the project) can be freely imported in any project module. If your contribution absolutely requires a non-standard library, talk to the repository manager.
* Developers are encouraged to follow [the official code style for Python PEP 0008](https://www.python.org/dev/peps/pep-0008/) as close as possible, although it is not mandated for the most part. The following sections are expected:
  - Follow [indentation](https://www.python.org/dev/peps/pep-0008/#indentation), [spaces](https://www.python.org/dev/peps/pep-0008/#tabs-or-spaces), and [maximum length](https://www.python.org/dev/peps/pep-0008/#maximum-line-length) guidelines. The guideline for line length in this project is break lines that extend beyond 100 characters (not 79 or 99), except if they are an example of a command use in an OOC command documentation string (in which case they may go over 100 characters).
* New classes, methods, helper functions should be accompanied by meaningful documentation in the form of inline comments and docstrings as needed. This project recommends the following documentation guidelines:
  - For commands in `server/commands.py`, each command should have a docstring detailing the following in order: if there is a rank restriction, its main purpose, different functionality in different cases if needed, expected syntax, meaning of arguments, and example uses.
  - For every other module, follow the [Numpy style](https://numpydoc.readthedocs.io/en/latest/format.html) for docstrings.
* Developers are encouraged to modify existing code that violates these guidelines so that they satisfy them. Seeing code that does not follow the guidelines is not an excuse not to use them for new code.
* The `TsuserverDR` class in `server/tsuserver.py` contains a few fields regarding version number. All pull requests should update these fields as follows, taking as reference the last commit of their target branch:
  - For a primary release, increase `self.release` by 1, set `self.major_release` to 0, set `self.minor_release` to 0 (all of these are to be done only if not previously done at the beginning of a development phase), and clear out `self.segment_version` if it is not empty.
  - For a major release, increase `self.major_release` by 1 and set `self.minor_release` to 0 (all of these are to be done only if not previously done at the beginning of a development phase), and clear out `self.segment_version` if it is not empty.
  - For a minor release, increase `self.minor_release` by 1 (only if not previously done at the beginning of a development phase), and clear out `self.segment_version` if it is not empty.
  - For a post-release, set `self.segment_version` to `post1` if it is empty, or increase its number by 1 otherwise.
  - For an alpha release, set `self.segment_version` to `a1` if it is empty, or increase its number by 1 otherwise. If the latter is performed, update primary/major/minor to the target version according to the development plan.
  - For a beta release, set `self.segment_version` to `b1` if it this is the first beta version, or increase its number by 1 otherwise.
  - For a release candidate, set `self.segment_version` to `RC1` if this is the first release candidate, or increase its number by 1 otherwise.
  - For any release, update `self.internal_version` as follows: possibly a letter indicating stage of development, the first six digits should correspond to the date of the last commit of the pull request in the format `yymmdd`; and a letter indicating number of commits in the target branch.
    - If a release is targeted towards an approved development branch, include one of the following letters at the beginning of the internal version.
      - `P` if the development branch is for a primary release (e.g. `P200101a`).
      - `M` if the development branch is for a major release (e.g. `M200319b`).
      - `m` if the development branch is for a minor release (e.g. `m200229c`).
      - `p` if the development branch is for a post-release (e.g. `p191231e`).
    - If a release is meant to be made public effective immediately, there should be no letters at the beginning (e.g. `200319a`).
    - The date should correspond to its equivalent EST/EDT date, whichever is active in the United States (so a person three hours behind EST, whose last commit in the pull request is at 10 pm, should add one to their day as it would be the next day in EST).
      - For example, a January 13, 2019 EST commit could be labeled `190113e`; and a December 7, 2020 EST commit could be labeled `201207a`.
    - The final letter should correspond to the `i`-th letter of the English alphabet, where `i` corresponds to however many releases were pushed to the target branch on that date.
      - For example, `201207a` means the release is the first one to the master branch of December 7, 2020; and `M190101c` is the third commit to the development branch in major release stage of January 1, 2019.
* To decide what sort of release your new contribution should be categorized as, follow these points:
  - If your release is meant to be made public effective immediately:
    - A primary release will massively overhaul most (if not all) existing code. It will likely massively break backwards compatibility.
    - A major release may introduce large new features and fix bugs. It may also break backwards compatibility in some minor ways.
    - A minor release may introduce small new features and fix bugs. It may also start announcing planned backwards incompatible changes.
    - A post-release only fixes bugs introduced in the latest public version.
  - If your release is meant to be for development:
    - An alpha release may introduce partial work on new features and fix bugs. No matter what, the first release of a development phase will be an alpha release.
	- A beta release may not start introducing code for brand new features, but may minorly expand code for features developed during the alpha period as well as fix code for features introduced earlier in development or earlier. Once in beta, no more alpha releases will be allowed.
	- A release candidate may not start or expand on existing features, but may fix code for features introduced earlier in development or even earlier. Once in release candidate phase, no more beta releases will be allowed.

## Best coding practices for YAML code
* Indent with 2 spaces if needed.
* Add comments describing keys and possible values.
* Developers are encouraged to modify existing code that violates these guidelines so that they satisfy them. Seeing code that does not follow the guidelines is not an excuse not to use them for new code.