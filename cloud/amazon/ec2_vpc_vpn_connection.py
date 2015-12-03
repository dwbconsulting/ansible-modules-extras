#!/usr/bin/python
#
# This is a free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This Ansible library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = """
---
module: ec2_vpc_vpn_connection
short_description: create or remove a vpn connection
description:
    - create or remove a vpn connection
version_added: "2.1"
author: Kristian Jones (@klj613)
options:
  name:
    description:
      - Unique name of the vpn connection
    required: true
  type:
    description:
      - The type of the vpn connection
    required: true
  customer_gateway_id:
    description:
      - ID of the customer gateway id
    required: true
  vpn_gateway_id:
    description:
      - ID of the customer gateway id
    required: true
  static_routes_only:
    description:
      - Use static routes only instead of dynamic
    required: false
    default: false
  wait:
    description:
      - Have ansible wait until the vpn connection is fully ready
    required: false
    default: false
  wait_timeout:
    description:
      - How long to wait until the vpn connection is fully ready
    required: false
    default: 300
  state:
    description:
      - The desired state of the vpn connection
    required: false
    default: present
    choices: [ 'present', 'absent' ]
  region:
    description:
      - The AWS region to use.  Must be specified if ec2_url is not used. If not specified then the value of the EC2_REGION environment variable, if any, is used.
    required: false
    default: null
    aliases: ['aws_region', 'ec2_region']
  aws_secret_key:
    description:
      - AWS secret key. If not set then the value of the AWS_SECRET_KEY environment variable is used.
    required: false
    default: None
    aliases: ['ec2_secret_key', 'secret_key']
  aws_access_key:
    description:
      - AWS access key. If not set then the value of the AWS_ACCESS_KEY environment variable is used.
    required: false
    default: None
    aliases: ['ec2_access_key', 'access_key']

requirements: [ "boto" ]
"""

EXAMPLES = '''
# Note: These examples do not set authentication details, see the AWS Guide for details.

- name: create vpn connection
  ec2_vpc_vpn_connection:
    name: vpn-1
    state: present
    customer_gateway_id: 'id_of_the_customer_gateway'
    vpn_gateway_id: 'id_of_the_customer_gateway'
    state_routes_only: True
    wait: True
  register: vpn
'''

RETURN = '''
connection_id:
    description: the id of the vpn connection
    returned: success
'''

import sys
import time

try:
    import boto.ec2
    import boto.vpc
    import boto.exception
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

if not HAS_BOTO:
    module.fail_json(msg='boto required for this module')

def get_connection_state(vpc_conn, original_vpn_connection):
    """
    Check connection state

    vpc_conn: authenticated VPCConnection connection object
    original_vpn_connection: the original vpn connection object

    returns string representation of the state of the vpn connection
    """
    vpn_connection_ids = [original_vpn_connection.id]
    vpn_connection = vpc_conn.get_all_vpn_connections(vpn_connection_ids)

    return vpn_connection[0].state

def await_vpn_connection_state(module, vpc_conn, vpn_connection, awaited_state, timeout):
    """
    Wait for an vpn connection to change state

    vpc_conn: authenticated VPCConnection connection object
    vpn_connection: vpn connection object
    awaited_state: state to poll for (string)
    timeout: how long to wait for the change to happen
    """

    wait_timeout = time.time() + timeout
    initial_state = get_connection_state(vpc_conn, vpn_connection)

    changed = False

    while True:
        connection_state = get_connection_state(vpc_conn, vpn_connection)

        if connection_state == awaited_state:
            if connection_state != initial_state:
                changed = True
            break
        elif connection_state == 'pending':
            pass
        elif time.time() >= wait_timeout:
            msg = "The vpn connection %s failed to be in the %s state within the timeout period."
            module.fail_json(msg=msg % (vpn_connection.id, awaited_state))
        time.sleep(1)

def create_vpn_connection(module, ec2, vpc_conn):
    """
    Creates a vpn connection

    module: Ansible module object
    ec2: authenticated ec2 connection object
    vpc_conn: authenticated VPCConnection connection object
    name: the option set name
    type: the type of vpn connection
    customer_gateway_id: the id of the customer gateway
    vpn_gateway_id: the id of the vpn gateway
    static_routes_only: indicates whether the VPN connection requires static routes.
    wait: True/False indicating to wait for the VPN to be in the available state
    wait_timeout: The timeout for waiting

    Returns a tuple
    """
    name = module.params.get('name')
    type = module.params.get('type')
    customer_gateway_id = module.params.get('customer_gateway_id')
    vpn_gateway_id = module.params.get('vpn_gateway_id')
    static_routes_only = module.params.get('static_routes_only')
    wait = module.params.get('wait')
    wait_timeout = module.params.get('wait_timeout')

    vpn_connections = vpc_conn.get_all_vpn_connections()

    for vpn_connection in vpn_connections:
        filters = {'resource-id': vpn_connection.id}
        gettags = ec2.get_all_tags(filters=filters)
        tagdict = {}
        for tag in gettags:
            tagdict[tag.name] = tag.value

        if ('Name', name) in set(tagdict.items()):
            changed = False

            if type != vpn_connection.type:
                changed = True
            if customer_gateway_id != vpn_connection.customer_gateway_id:
                changed = True
            if vpn_gateway_id != vpn_connection.vpn_gateway_id:
                changed = True

            # cant seem to get the routing type to check if that has changed

            if changed:
                module.fail_json(msg='VPN connection cannot be modified')

            return (vpn_connection.id, False)

    vpn_connection = vpc_conn.create_vpn_connection(type, customer_gateway_id, vpn_gateway_id, static_routes_only)
    ec2.create_tags(vpn_connection.id, {'Name': name})

    if wait:
        await_vpn_connection_state(module, vpc_conn, vpn_connection, 'available', wait_timeout)

    return (vpn_connection.id, True)

def delete_vpn_connection(module, ec2, vpc_conn):
    """
    Deletes a vpn connection

    module: Ansible module object
    ec2: authenticated ec2 connection object
    vpc_conn: authenticated VPCConnection connection object
    name: the option set name

    Returns a list of the DHCP options that have been deleted
    """

    name = module.params.get('name')

    vpn_connections = vpc_conn.get_all_vpn_connections()
    removed_vpn_connections = []

    for vpn_connection in vpn_connections:
        filters = {'resource-id': vpn_connection.id}
        gettags = ec2.get_all_tags(filters=filters)
        tagdict = {}
        for tag in gettags:
            tagdict[tag.name] = tag.value

        if ('Name', name) in set(tagdict.items()):
            vpc_conn.delete_vpn_connection(vpn_connection.id)

            removed_vpn_connections.append(vpn_connection.id)
    
    return removed_vpn_connections

def main():
    """
    Module entry point.
    """
    arguent_spec = ec2_argument_spec()
    arguent_spec.update(dict(
        name=dict(required=True),
        type=dict(required=True),
        customer_gateway_id=dict(required=True),
        vpn_gateway_id=dict(required=True),
        static_routes_only=dict(default=False, required=False),
        wait=dict(default=False, required=False),
        wait_timeout=dict(default=300, required=False),
        state=dict(choices=['present', 'absent'], default='present')
        ))

    module = AnsibleModule(
        argument_spec=arguent_spec,
    )

    state = module.params.get('state')
    _, aws_access_key, aws_secret_key, region = get_ec2_creds(module)

    if region:
        try:
            vpc_conn = boto.vpc.connect_to_region(
                region,
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key
            )

            ec2 = ec2_connect(module)
        except boto.exception.NoAuthHandlerFound, ex:
            module.fail_json(msg=str(ex))
    else:
        module.fail_json(msg="region must be specified")

    if state == 'present':
        (connection, changed) = create_vpn_connection(module, ec2, vpc_conn)
        module.exit_json(changed=changed, connection_id=connection)
    elif state == 'absent':
        removed = delete_vpn_connection(module, ec2, vpc_conn)
        changed = (len(removed) > 0)
        module.exit_json(changed=changed, removed_ids=removed)

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *
main()
