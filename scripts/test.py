#!/usr/bin/env python3

from pprint import pprint

from waybar.util import network

foo = network.get_network_data()
pprint(foo)
