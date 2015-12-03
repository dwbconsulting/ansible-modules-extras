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
module: ec2_vpc_customer_gateway
short_description: create or remove a vpc customer gateway
description:
    - create or remove a vpc customer gateway
version_added: "2.1"
author: Kristian Jones (@klj613)
options:
  name:
    description:
      - Unique name of the customer gateway
    required: true
  type:
    description:
      - The type of the customer gateway
    required: true
  ip_address:
    description:
      - The IP address setting for the customer gateway
    required: true
  bgp_asn:
    description:
      - The BGP ASN setting for the customer gateway
    required: true
  state:
    description:
      - The desired state of the customer gateway
    required: true
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

- name: create customer gateway
  ec2_vpc_customer_gateway:
    name: cgw-1
    state: present
    type: ipsec.1
    ip_address: '127.0.0.1'
    bgp_asn: 65000
  register: cgw
'''

RETURN = '''
gateway_id:
    description: the id of the customer gateway
    returned: success
'''

import sys

try:
    import boto.ec2
    import boto.vpc
    import boto.exception
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

if not HAS_BOTO:
    module.fail_json(msg='boto required for this module')

def create_customer_gateway(module, ec2, vpc_conn):
    """
    Creates a customer gateway

    module: Ansible module object
    ec2: authenticated ec2 connection object
    vpc_conn: authenticated VPCConnection connection object
    name: the option set name
    type: type of the customer gateway
    ip_address: ip address
    bgp_asn: bgp value as a integer

    Returns a tuple
    """
    name = module.params.get('name')
    type = module.params.get('type')
    ip_address = module.params.get('ip_address')
    bgp_asn = module.params.get('bgp_asn')

    customer_gateways = vpc_conn.get_all_customer_gateways()

    for customer_gateway in customer_gateways:
        filters = {'resource-id': customer_gateway.id}
        gettags = ec2.get_all_tags(filters=filters)
        tagdict = {}
        for tag in gettags:
            tagdict[tag.name] = tag.value

        if ('Name', name) in set(tagdict.items()):
            changed = False

            if type != customer_gateway.type:
                changed = True
            if ip_address != customer_gateway.ip_address:
                changed = True
            if bgp_asn != customer_gateway.bgp_asn:
                changed = True

            if changed:
                module.fail_json(msg='Customer gateway cannot be modified')

            return (customer_gateway.id, False)

    customer_gateway = vpc_conn.create_customer_gateway(type, ip_address, bgp_asn)
    ec2.create_tags(customer_gateway.id, {'Name': name})

    return (customer_gateway.id, True)

def delete_customer_gateway(module, ec2, vpc_conn):
    """
    Deletes a customer gateway

    module: Ansible module object
    ec2: authenticated ec2 connection object
    vpc_conn: authenticated VPCConnection connection object
    name: the option set name

    Returns a list of the DHCP options that have been deleted
    """

    name = module.params.get('name')

    customer_gateways = vpc_conn.get_all_customer_gateways()
    removed_customer_gateways = []

    for customer_gateway in customer_gateways:
        filters = {'resource-id': customer_gateway.id}
        gettags = ec2.get_all_tags(filters=filters)
        tagdict = {}
        for tag in gettags:
            tagdict[tag.name] = tag.value

        if ('Name', name) in set(tagdict.items()):
            vpc_conn.delete_customer_gateway(customer_gateway.id)

            removed_customer_gateways.append(customer_gateway.id)
    
    return removed_customer_gateways

def main():
    """
    Module entry point.
    """
    arguent_spec = ec2_argument_spec()
    arguent_spec.update(dict(
        name=dict(required=True),
        type=dict(required=True),
        ip_address=dict(required=True),
        bgp_asn=dict(required=True, type='int'),
        state=dict(choices=['present', 'absent'], default='present'),
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
        (connection, changed) = create_customer_gateway(module, ec2, vpc_conn)
        module.exit_json(changed=changed, gateway_id=connection)
    elif state == 'absent':
        removed = delete_customer_gateway(module, ec2, vpc_conn)
        changed = (len(removed) > 0)
        module.exit_json(changed=changed, removed_ids=removed)

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *
main()
