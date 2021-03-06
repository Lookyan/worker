from ..client import ResponseStructureError
from ..client import InvalidJSONError
from .base import Base


DAYS_OF_WEEK = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
STATE_OK = 'OK'
STATE_WARN = 'WARN'
STATE_ERROR = 'ERROR'
STATE_NODATA = 'NODATA'
STATE_EXCEPTION = 'EXCEPTION'

MINUTES_IN_HOUR = 60


class Trigger(Base):

    def __init__(
            self,
            client,
            name,
            targets,
            desc='',
            warn_value=None,
            error_value=None,
            tags=None,
            ttl='600',
            ttl_state=STATE_NODATA,
            sched=None,
            expression='',
            **kwargs):
        """

        :param client: api client
        :param name: str trigger name
        :param targets: list of str targets
        :param desc: str trigger description
        :param warn_value: int warning value (if T1 <= warn_value)
        :param error_value: int error value (if T1 <= error_value)
        :param tags: list of str tags for trigger
        :param ttl: str set ttl_state if has no value for ttl seconds
        :param ttl_state: str state after ttl seconds without data (one of STATE_* constants)
        :param sched: dict schedule for trigger
        :param expression: str python expression
        :param kwargs: additional parameters
        """
        self._client = client

        self._id = kwargs.get('id', None)
        self.name = name
        self.desc = desc
        self.targets = targets
        self.warn_value = warn_value
        self.error_value = error_value
        self.ttl = ttl
        self.ttl_state = ttl_state
        if not tags:
            tags = []
        self.tags = tags
        default_sched = {
            'startOffset': 0,
            'endOffset': 1439,
            'tzOffset': -180
        }
        if not sched:
            sched = default_sched
            self.disabled_days = set()
        else:
            if 'days' in sched:
                self.disabled_days = {day['name'] for day in sched['days'] if not day['enabled']}
        self.sched = sched
        self.expression = expression

        # compute time range
        self._start_hour = self.sched['startOffset'] // MINUTES_IN_HOUR
        self._start_minute = self.sched['startOffset'] - self._start_hour * MINUTES_IN_HOUR
        self._end_hour = self.sched['endOffset'] // MINUTES_IN_HOUR
        self._end_minute = self.sched['endOffset'] - self._end_hour * MINUTES_IN_HOUR

    def add_target(self, target):
        """
        Add pattern name
        :param target: str target pattern
        :return: None
        """
        self.targets.append(target)

    def add_tag(self, tag):
        """
        Add tag to trigger
        :param tag: str tag name
        :return: None
        """
        self.tags.append(tag)

    def disable_day(self, day):
        """
        Disable day

        :param day: str one of DAYS_OF_WEEK
        :return: None
        """
        self.disabled_days.add(day)

    def enable_day(self, day):
        """
        Enable day

        :param day: str one of DAYS_OF_WEEK
        :return: None
        """
        self.disabled_days.remove(day)

    @property
    def id(self):
        return self._id

    def _send_request(self, trigger_id=None):
        data = {
            'name': self.name,
            'desc': self.desc,
            'targets': self.targets,
            'warn_value': self.warn_value,
            'error_value': self.error_value,
            'ttl': self.ttl,
            'ttl_state': self.ttl_state,
            'tags': self.tags,
            'sched': self.sched,
            'expression': self.expression
        }

        if trigger_id:
            data['id'] = trigger_id

        data['sched']['days'] = []
        for day in DAYS_OF_WEEK:
            day_info = {
                'enabled': True if day not in self.disabled_days else False,
                'name': day
            }
            data['sched']['days'].append(day_info)

        data['sched']['startOffset'] = self._start_hour * MINUTES_IN_HOUR + self._start_minute
        data['sched']['endOffset'] = self._end_hour * MINUTES_IN_HOUR + self._end_minute

        if trigger_id:
            res = self._client.put('trigger/' + trigger_id, json=data)
        else:
            res = self._client.put('trigger', json=data)
        if 'id' not in res:
            raise ResponseStructureError('id not in response', res)
        self._id = res['id']
        return self._id

    def save(self):
        """
        Save trigger

        :return: trigger_id
        """
        if self._id:
            return self.update()
        return self._send_request()

    def update(self):
        """
        Update trigger

        :return: trigger id
        """
        return self._send_request(self._id)

    def set_start_hour(self, hour):
        """
        Set start hour

        :param hour: int hour

        :return: None
        """
        self._start_hour = hour

    def set_start_minute(self, minute):
        """
        Set start minute

        :param minute: int minute

        :return: None
        """
        self._start_minute = minute

    def set_end_hour(self, hour):
        """
        Set end hour

        :param hour: int hour

        :return: None
        """
        self._end_hour = hour

    def set_end_minute(self, minute):
        """
        Set end minute

        :param minute: int minute

        :return: None
        """
        self._end_minute = minute


class TriggerManager:
    def __init__(self, client):
        self._client = client

    @property
    def trigger_client(self):
        return self._client

    def fetch_all(self):
        """
        Returns all existing triggers

        :return: list of Trigger

        :raises: ResponseStructureError
        """
        result = self._client.get(self._full_path())
        if 'list' in result:
            triggers = []
            for trigger in result['list']:
                triggers.append(Trigger(self._client, **trigger))
            return triggers
        else:
            raise ResponseStructureError("list doesn't exist in response", result)

    def fetch_by_id(self, trigger_id):
        """
        Returns Trigger by trigger id
        :param trigger_id: str trigger id
        :return: Trigger
        """
        result = self._client.get(self._full_path())
        if 'list' in result:
            for trigger in result['list']:
                if 'id' in trigger:
                    if trigger['id'] == trigger_id:
                        return Trigger(self._client, **trigger)

    def delete(self, trigger_id):
        """
        Delete trigger by trigger id
        :param trigger_id: str trigger id
        :return: True if deleted, False otherwise
        """
        try:
            self._client.delete(self._full_path(trigger_id))
            return True
        except InvalidJSONError:
            return False

    def reset_throttling(self, trigger_id):
        """
        Resets throttling by trigger id
        :param trigger_id: str trigger id
        :return: True if reset, False otherwise
        """
        try:
            self._client.delete(self._full_path(trigger_id + '/throttling'))
            return True
        except InvalidJSONError:
            return False

    def get_state(self, trigger_id):
        """
        Get state of trigger by trigger id
        :param trigger_id: str trigger id
        :return: state of trigger
        """
        return self._client.get(self._full_path(trigger_id + '/state'))

    def remove_metric(self, trigger_id, metric):
        """
        Remove metric by trigger id
        :param trigger_id: str trigger id
        :param metric: str metric name
        :return: True if removed, False otherwise
        """
        try:
            params = {
                'name': metric
            }
            self._client.delete(self._full_path(trigger_id + '/metrics'), params=params)
            return True
        except InvalidJSONError:
            return False

    def create(
            self,
            name,
            targets,
            desc='',
            warn_value=None,
            error_value=None,
            tags=None,
            ttl='600',
            ttl_state=STATE_NODATA,
            sched=None,
            expression='',
            **kwargs
    ):
        """
        Creates new trigger. To save it call save() method of Trigger.
        :param name: str trigger name
        :param targets: list of str targets
        :param desc: str trigger description
        :param warn_value: int warning value (if T1 <= warn_value)
        :param error_value: int error value (if T1 <= error_value)
        :param tags: list of str tags for trigger
        :param ttl: str set ttl_state if has no value for ttl seconds
        :param ttl_state: str state after ttl seconds without data (one of STATE_* constants)
        :param sched: dict schedule for trigger
        :param expression: str python expression
        :param kwargs: additional trigger params
        :return: Trigger
        """
        return Trigger(
            self._client,
            name,
            targets,
            desc,
            warn_value,
            error_value,
            tags,
            ttl,
            ttl_state,
            sched,
            expression,
            **kwargs
        )

    def _full_path(self, path=''):
        return 'trigger/' + path
