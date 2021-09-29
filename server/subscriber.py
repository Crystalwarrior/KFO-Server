# TsuserverDR, a Danganronpa Online server based on tsuserver3, an Attorney Online server
#
# Copyright (C) 2016 argoneus <argoneuscze@gmail.com> (original tsuserver3)
# Current project leader: 2018-21 Chrezm/Iuvee <thechrezm@gmail.com>
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

"""
Module that implements a simple publisher-listener model.
"""


class Listener:
    """
    A listener may be subscribed to many publishers, so it will be receiving messages from them.
    When a listener receives one such message from one of the publishers it is subscribed to, it
    may perform some action based on an event directory, which maps message names to actions.
    """

    # (Private) Attributes
    # --------------------
    # _parent : Any
    #     Parent of the listener (that is, parent.listener == self).
    # _event_directory : dict of str to method
    #     Map of message names to actions to perform on message receipt.
    # _subscriptions : list of Publisher
    #     Publishers this listener are subscribed to.

    def __init__(self, parent, event_directory):
        """
        Create a new listener.

        Parameters
        ----------
        parent : Any
            Object the listener is attached to (that is, parent.listener == self).
        event_directory : dict of str to method
            Map of message names to actions to perform on message receipt.

        Returns
        -------
        None.

        """

        self._parent = parent
        self._event_directory = event_directory.copy()
        self._subscriptions = list()
        # self._subscriptions is modified only by publishers

    @staticmethod
    def _get_publisher(_object):
        """
        Return the standard publisher of an object (_object.publisher)

        Parameters
        ----------
        _object : Any
            Object whose standard publisher will be procured.

        Raises
        ------
        AttributeError
            If the object has no standard publisher.

        Returns
        -------
        Publisher
            Standard publisher of the object.

        """

        try:
            return _object.publisher
        except AttributeError:
            raise AttributeError(f'{_object} lacks a standard publisher object.')

    def subscribe(self, subscribing_to):
        """
        Subscribe this listener to an object's publisher. This is equivalent to
        subscribing_to.publisher.add(self). If the listener is already subscribed, this method
        does nothing.

        Parameters
        ----------
        subscribing_to : Any
            Object to subscribe to.

        Raises
        ------
        AttributeError
            If the object is not setup to publish.

        Returns
        -------
        None.

        """

        publisher = self._get_publisher(subscribing_to)
        publisher.add(self._parent)

    def unsubscribe(self, unsubscribing_from):
        """
        Unsubscribe this listener from an object's publisher. This is equivalent to
        subscribing_to.publisher.discard(self). If the listener is already unsubscribed, this
        method
        does nothing.

        Parameters
        ----------
        unsubscribing_from : Any
            Object to unsubscribe from.

        Raises
        ------
        AttributeError
            If the object is not setup to publish.

        Returns
        -------
        None.

        """

        publisher = self._get_publisher(unsubscribing_from)
        publisher.discard(self._parent)

    def get_subscriptions(self):
        """
        Return (a shallow copy of) the publishers this listener is subscribed to.

        Returns
        -------
        list of Publisher.
            Subscribed-to publishers.

        """

        return self._subscriptions.copy()

    def is_subscribed_to(self, other):
        """
        If the listner is subscribed to other, return True; otherwise, return False.

        Parameters
        ----------
        other : Any
            Object to test (not its publisher).

        Raises
        ------
        AttributeError
            If the object is not setup to publish.

        Returns
        -------
        bool
            True if subscribed, False otherwise.

        """

        publisher = self._get_publisher(other)
        return publisher in self._subscriptions

    def get_parent(self):
        """
        Return the parent of the listener.

        Returns
        -------
        Any
            Parent of the listener.

        """

        return self._parent

    def update_events(self, new_events):
        """
        Update the event directory of the listener with new events (Python dictionary update).

        Parameters
        ----------
        new_events : dict of str to method
            New actions to include in the event directory.

        Returns
        -------
        None.

        """

        self._event_directory.update(new_events)

    def perform(self, source, name, arguments):
        """
        Perform an action based on the message name and arguments if the listener's event directory
        has an associated action for that type of message. If the listener does not have an
        associated event for the message, this method does nothing.

        Parameters
        ----------
        source : Any
            Object that published the transmission (not its publisher, the object's publisher).
        name : str
            Name of the message.
        arguments : dict of str to Any
            Keyword arguments of the associated method.

        Returns
        -------
        None.

        """

        try:
            method = self._event_directory[name]
        except KeyError:
            return
        else:
            method(source, **arguments)

class Publisher:
    """
    A publisher maintains a list of listeners, to whom it may send messages. Each message has
    a name and arguments. Listeners are sent messages in order of subscription: listeners who
    subscribed earlier are sent a message before listeners who subscribed later.
    """

    # (Private) Attributes
    # --------------------
    # _parent : Any
    #     Parent of the publisher (that is, parent.publisher == self).
    # _listeners : list of Listener
    #     Listener objects to whom messages will be sent.

    def __init__(self, parent):
        """
        Create a new publisher.

        Parameters
        ----------
        parent : Any
            Object the publisher is attached to (that is, publisher.listener == self).

        Returns
        -------
        None.

        """

        self._parent = parent
        self._listeners = list()

    @staticmethod
    def _get_listener(_object):
        """
        Return the standard listener of an object (_object.listener)

        Parameters
        ----------
        _object : Any
            Object whose standard listener will be procured.

        Raises
        ------
        AttributeError
            If the object has no standard listener.

        Returns
        -------
        Listener
            Standard listener.

        """

        try:
            return _object.listener
        except AttributeError:
            raise AttributeError(f'{_object} lacks a listener object.')

    def add(self, new_subscriber):
        """
        Make an object listen to this publisher's future messages. If the object is already setup
        to listen, this method does nothing.

        Parameters
        ----------
        new_subscriber : Any
            Object to test.

        Raises
        ------
        AttributeError
            If the object is not setup to listen.

        Returns
        -------
        None.

        """

        listener = self._get_listener(new_subscriber)
        if listener not in self._listeners:
            self._listeners.append(listener)
        if self not in listener._subscriptions:
            listener._subscriptions.append(self)

    def discard(self, subscriber):
        """
        Make an object no longer listen to this publisher's future messages. If the object is
        already setup to not listen, this method does nothing.

        Parameters
        ----------
        subscriber : Any
            Object to test.

        Raises
        ------
        AttributeError
            If the object is not setup to listen.

        Returns
        -------
        None.

        """

        listener = self._get_listener(subscriber)
        if listener in self._listeners:
            self._listeners.remove(listener)
        if self in listener._subscriptions:
            listener._subscriptions.remove(self)

    def get_subscribers(self):
        """
        Return (a shallow copy of) the listeners subscribed to this publisher.

        Returns
        -------
        list of Listeners.
            Subscribed listeners.

        """

        return self._listeners.copy()

    def has_subscriber(self, other):
        """
        If the publisher has other as a subscriber, return True; otherwise, return False.

        Parameters
        ----------
        other : Any
            Object to test (not its listener).

        Raises
        ------
        AttributeError
            If the object is not setup to listen.

        Returns
        -------
        bool
            True if subscriber, False otherwise.

        """

        listener = self._get_listener(other)
        return listener in self._listeners

    def get_parent(self):
        """
        Return the parent of the publisher.

        Returns
        -------
        Any
            Parent of the publisher.

        """

        return self._parent

    def publish(self, name, arguments):
        """
        Send a message to this publisher's subscribers.

        Parameters
        ----------
        name : str
            Name of message.
        arguments : Dict of str to Any
            Arguments of the message.

        Returns
        -------
        None.

        """

        for listener in self.get_subscribers():
            listener.perform(self._parent, name, arguments)
