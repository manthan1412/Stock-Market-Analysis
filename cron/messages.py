from enum import Enum


class MessageParameters(Enum):
    SYMBOL = 0
    INTERVAL = 1
    BEGIN_DATETIME = 2
    END_DATETIME = 3
    MAX_DATAPOINTS = 4
    BEGIN_FILTER_TIME = 5
    END_FILTER_TIME = 6
    DATA_DIRECTION = 7
    REQUEST_ID = 8
    DATAPOINTS_PER_SECOND = 9
    INTERVAL_TYPE = 10
    LABEL_AT_BEGINNING = 11
    MAX_DAYS_OF_DATAPOINTS = 12
    RESERVED = 13
    UPDATE_INTERVAL = 14


class IntervalType(Enum):
    SECONDS = 0
    DAILY = 1


class MessageType(Enum):
    HIT = 0
    HDT = 1
    HWX = 2
    BW = 3


message_parameters = {
    MessageType.HIT: [MessageParameters.SYMBOL,
                      MessageParameters.INTERVAL,
                      MessageParameters.BEGIN_DATETIME,
                      MessageParameters.END_DATETIME,
                      MessageParameters.MAX_DATAPOINTS,
                      MessageParameters.BEGIN_FILTER_TIME,
                      MessageParameters.END_FILTER_TIME,
                      MessageParameters.DATA_DIRECTION,
                      MessageParameters.REQUEST_ID,
                      MessageParameters.DATAPOINTS_PER_SECOND,
                      MessageParameters.INTERVAL_TYPE],
                      # MessageParameters.LABEL_AT_BEGINNING],
    MessageType.HDT: [MessageParameters.SYMBOL,
                      MessageParameters.BEGIN_DATETIME,
                      MessageParameters.END_DATETIME,
                      MessageParameters.MAX_DATAPOINTS,
                      MessageParameters.DATA_DIRECTION,
                      MessageParameters.REQUEST_ID,
                      MessageParameters.DATAPOINTS_PER_SECOND],
    MessageType.HWX: [MessageParameters.SYMBOL,
                      MessageParameters.MAX_DATAPOINTS,
                      MessageParameters.DATA_DIRECTION,
                      MessageParameters.REQUEST_ID,
                      MessageParameters.DATAPOINTS_PER_SECOND],
    MessageType.BW: [MessageParameters.SYMBOL,
                     MessageParameters.INTERVAL,
                     MessageParameters.BEGIN_DATETIME,
                     MessageParameters.MAX_DAYS_OF_DATAPOINTS,
                     MessageParameters.MAX_DATAPOINTS,
                     MessageParameters.BEGIN_FILTER_TIME,
                     MessageParameters.END_FILTER_TIME,
                     MessageParameters.REQUEST_ID,
                     MessageParameters.INTERVAL_TYPE,
                     MessageParameters.RESERVED,
                     MessageParameters.UPDATE_INTERVAL]
}


defaults = {
    MessageParameters.BEGIN_DATETIME: "",
    MessageParameters.END_DATETIME: "",
    MessageParameters.MAX_DATAPOINTS: "",
    MessageParameters.BEGIN_FILTER_TIME: "",
    MessageParameters.END_FILTER_TIME: "",
    MessageParameters.DATA_DIRECTION: "0",
    MessageParameters.REQUEST_ID: "",
    MessageParameters.DATAPOINTS_PER_SECOND: "100",
    MessageParameters.INTERVAL_TYPE: 's',
    MessageParameters.LABEL_AT_BEGINNING: '1',
    MessageParameters.UPDATE_INTERVAL: '0'
}


class IQfeedMessage(object):

    def __init__(self, message_type, parameters):
        self.message_type = message_type
        self.p = parameters
        self.__sanity_check()
        self.parameters = \
            [self.__get_parameter(message_parameter)for message_parameter in message_parameters[message_type]]

    @staticmethod
    def get_message_parameter(message_type):
        if message_type in message_map:
            return message_parameters[message_type]
        return "Message type {} is not supported".format(message_type)

    @staticmethod
    def get_supported_method_types():
        return list(message_map.keys())

    def get_message(self):
        return "{0},{1}\r\n".format(self.message_type.name, ",".join(self.parameters))

    def __sanity_check(self):
        if not isinstance(self.message_type, MessageType):
            raise TypeError("message_type must be an instance of MessageType enum")
        if MessageParameters.SYMBOL not in self.p:
            raise ValueError("You must set MessageParameters.SYMBOL in parameters")
        if self.message_type != MessageType.HWX \
                and MessageParameters.BEGIN_DATETIME not in self.p \
                and MessageParameters.END_DATETIME not in self.p:
            raise ValueError("At least one of MessageParameters.BEGIN_DATETIME or MessageParameters.END_DATETIME should"
                             " be set")

    def __get_parameter(self, message_parameter):
        if message_parameter in self.p:
            return self.p[message_parameter]
        return defaults[message_parameter] if message_parameter in defaults else ""
