#! /opt/local/bin/python3.6
"""Event handlers for VOEvents."""

import logging

from . import database as db
from . import slack
from .events import Event


def event_handler(event, send_messages=False, log=None):
    """Handle a new Event.

    Returns the Event if it is interesting, or None if it's been rejected.

    Parameters
    ----------
    send_messages : bool, optional
        If True, send Slack messages.
        Default is False.

    """
    # Create a logger if one isn't given
    if log is None:
        logging.basicConfig(level=logging.DEBUG)
        log = logging.getLogger('goto-alert')

    # Log IVORN
    log.info('Handling Event {}'.format(event.ivorn))

    # Check if it's an event we want to process, otherwise return None
    if not event.interesting:
        log.warning('Ignoring uninteresting event (type={}, role={})'.format(event.type,
                                                                             event.role))
        return None

    # It passed the checks: it's an interesting event!
    log.info('Processing interesting {} Event {}'.format(event.type, event.name))

    # Send initial Slack report
    if send_messages:
        log.debug('Sending initial Slack report')
        msg = '*Processing new {} {} event: {}*'.format(event.source, event.type, event.id)
        slack.send_slack_msg(msg)
        log.debug('Slack report sent')

    # Fetch the event skymap
    if hasattr(event, 'get_skymap'):
        # Not all "interesting" events will have a skymap (e.g. retractions)
        log.debug('Fetching event skymap')
        event.get_skymap()
        log.debug('Skymap created')

    # Send Slack event report
    if send_messages:
        log.debug('Sending Slack event report')
        slack.send_event_report(event)
        log.debug('Slack report sent')

    # Get the observing strategy for this event (stored on the event as event.strategy)
    # NB we can only do this after getting the skymap, because for GW events we need the distance.
    log.debug('Fetching event strategy')
    event.get_strategy()
    log.debug('Using strategy {}'.format(event.strategy['strategy']))

    # Send Slack strategy report
    if send_messages:
        log.debug('Sending Slack strategy report')
        slack.send_strategy_report(event)
        log.debug('Slack report sent')

    # Add the event into the GOTO observation DB
    log.info('Inserting event {} into GOTO database'.format(event.name))
    try:
        # First we need to see if there's a previous instance of the same event already in the db
        # If so, then delete any still pending pointings and mpointings assosiated with the event
        log.debug('Checking for previous events in database')
        db.remove_previous_events(event, log)

        # Then add the new pointings
        log.debug('Adding to database')
        db.add_to_database(event, log)
        log.info('Database insersion complete')

        # Send Slack database report
        if send_messages:
            log.debug('Sending Slack database report')
            slack.send_database_report(event)
            log.debug('Slack report sent')

    except Exception:
        log.warning('Unable to insert event into database')

        # Send Slack error report
        if send_messages:
            log.debug('Sending Slack error report')
            msg = '*ERROR*: Failed to insert event {} into database'.format(event.name)
            slack.send_slack_msg(msg)
            log.debug('Slack report sent')

        raise

    log.info('Event {} processed'.format(event.name))
    return event


def payload_handler(payload, send_messages=False):
    """Handle a VOEvent payload.

    Returns the Event if it is interesting, or None if it's been rejected.
    """
    # Create event from the payload
    event = Event.from_payload(payload)

    # Run the event handler
    event_handler(event, send_messages)
