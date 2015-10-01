import json
from jsonschema import validate
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from . import renderers
from .schema import schema
from ...exceptions import ValidationError

from jinja2 import Environment, PackageLoader


class OpenWrt(object):
    """ OpenWrt Backend """
    schema = schema
    renderers = [
        renderers.SystemRenderer,
        renderers.NetworkRenderer,
        renderers.WirelessRenderer,
        renderers.DefaultRenderer
    ]

    def __init__(self, config):
        """
        :param config: python dict containing a valid NetJSON DeviceConfiguration
        :raises TypeError: raises an exception if config is not an instance of dict
        """
        if not isinstance(config, dict):
            raise TypeError('Config argument must be an istance of dict or one of its subclasses')
        # allow omitting NetJSON type
        if 'type' not in config:
            config.update({'type': 'DeviceConfiguration'})
        self.config = config
        self.env = Environment(loader=PackageLoader('netjsonconfig.backends.openwrt', 'templates'),
                               trim_blocks=True)
        self.__find_bridges()

    def render(self):
        self.validate()
        output = ''
        for renderer_class in self.renderers:
            renderer = renderer_class(self)
            additional_output = renderer.render()
            # add an additional new line
            # to separate blocks
            if output and additional_output:
                output += '\n'
            output += additional_output
        return output

    def validate(self):
        try:
            validate(self.config, self.schema)
        except JsonSchemaValidationError as e:
            raise ValidationError(e)

    def json(self, *args, **kwargs):
        self.validate()
        return json.dumps(self.config, *args, **kwargs)

    @classmethod
    def get_packages(cls):
        return [r.get_package() for r in cls.renderers]

    def __find_bridges(self):
        """
        OpenWRT declare bridges in /etc/config/network
        but wireless interfaces are attached to ethernet ones
        with declarations that go in /etc/config/wireless
        this method populates a few auxiliary data structures
        that are used to generate the correct UCI bridge settings
        """
        wifi = {}
        bridges = {}
        net_bridges = {}
        for interface in self.config.get('interfaces', []):
            if interface.get('type') == 'wireless':
                wifi[interface['name']] = interface
            elif interface.get('type') == 'bridge':
                bridges[interface['name']] = interface['bridge_members']
        for bridge_members in bridges.values():
            # determine bridges that will go in /etc/config/network
            net_names = [name for name in bridge_members if name not in wifi.keys()]
            net_bridges[net_names[0]] = net_names
            # openwrt deals with wifi bridges differently
            for name in bridge_members:
                if name in wifi.keys():
                    wifi[name]['_attached'] = net_names
        self._net_bridges = net_bridges
