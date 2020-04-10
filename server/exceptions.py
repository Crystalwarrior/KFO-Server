# TsuserverDR, a Danganronpa Online server based on tsuserver3, an Attorney Online server
#
# Copyright (C) 2016 argoneus <argoneuscze@gmail.com> (original tsuserver3)
# Current project leader: 2018-19 Chrezm/Iuvee <thechrezm@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

# This whole class will be rewritten for 4.3

class TsuserverException(Exception):
    def __init__(self, message='', code=None):
        self.message = message
        if code:
            self.code = code

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        if self.message != other.message:
            return False
        return True

    @classmethod
    def subexceptions(cls):
        return [item for item in cls.__dict__.keys() if not item.startswith('__')]

    @classmethod
    def reset_subexceptions(cls):

        for subexception_name in cls.subexceptions():
            setattr(cls, subexception_name, type(subexception_name, (cls, ), dict()))

def recreate_subexceptions(cls):
    """
    Recreate all subexceptions so that their parent is the exception class itself, rather
    than TsuserverException.

    """
    subexceptions = [item for item in cls.__dict__.keys() if not item.startswith('__')]
    for subexception_name in subexceptions:
        fullname = '{}.{}'.format(cls.__name__, subexception_name)
        setattr(cls, subexception_name, type(fullname, (cls, ), dict()))
    return cls

@recreate_subexceptions
class ClientError(TsuserverException):
    class UnauthorizedError(TsuserverException):
        pass

class AreaError(TsuserverException):
    pass

class ArgumentError(TsuserverException):
    pass

@recreate_subexceptions
class ServerError(TsuserverException):
    class ServerFileNotFoundError(TsuserverException):
        pass

    class MusicNotFoundError(TsuserverException):
        pass

    class MusicInvalidError(TsuserverException):
        pass

    class MusicInvalid(TsuserverException):
        # Remove, kept for backwards compatibility
        pass

    class YAMLNotFoundError(TsuserverException):
        pass

    class YAMLInvalidError(TsuserverException):
        pass

class PartyError(TsuserverException):
    pass

@recreate_subexceptions
class ZoneError(TsuserverException):
    class AreaConflictError(TsuserverException):
        pass

    class AreaNotInZoneError(TsuserverException):
        pass

    class WatcherConflictError(TsuserverException):
        pass

    class WatcherNotInZoneError(TsuserverException):
        pass
