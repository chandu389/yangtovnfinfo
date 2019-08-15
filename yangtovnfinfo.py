import pprint
import sys
from xml.dom.minidom import parse, Document, parseString
import os
import logging
import argparse
import yaml
import json
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)


def read_yaml(file):
    log.info("Reading YAML file {}".format(file))
    f = open(file, 'rb')
    file_read = f.read()
    f.close()
    parsed_yaml = yaml.safe_load(file_read)

    return parsed_yaml

def read_json(file):
    f = open(file, 'rb')
    sol003json = json.load(f)

    return sol003json

class yangtovnfinfo:
    def __init__(self):
        self.variables = None
        self.tosca_lines = None
        self.tosca_vnf = None
        self.converter = None
        self.provider = None
        self.supported_providers = None
        self.cnfv = None

        self.desc = "Yang model to SOL6 Vnf Info Converter XML"

        parser = argparse.ArgumentParser(description=self.desc)
        parser.add_argument('-s1f', '--sol001file',
                            help="The sol001 yaml file to be processed")
        parser.add_argument('-tf', '--templatefile',
                            help="The sample vnf-info template file to be processed")
        parser.add_argument('-s3f', '--sol003file',
                            help="sol003 automation json")
        parser.add_argument('-o', '--output',
                            help="The output file for the generated VNF Info (XML format), "
                                 "outputs to stdout if not specified")
        parser.add_argument('-l', '--log-level',
                            choices=['DEBUG', 'INFO', 'WARNING'], default=logging.INFO,
                            help="Set the log level for standalone logging")
        # Advanced arguments:
        parser.add_argument('-v', '--vim', default="dmz_openstack_vim",
                            help="Vim connection")
        parser.add_argument('-z', '--zone_id', default="nova",
                            help="zone")

        args = parser.parse_args()

        self.args = args
        self.parser = parser

        if not args.sol001file or not args.templatefile:
            print("error: the following arguments are required: -sf/--sol001file, -tf/--templatefile")
            return

        # Initialize the log and have the level set properly
        setup_logger(args.log_level)

        self.vnfInfodom = parse(self.args.templatefile)
        self.parsed_yaml = read_yaml(self.args.sol001file)
        self.sol003json = read_json(self.args.sol003file)
        self.vnfInfo_ele = self.vnfInfodom.getElementsByTagName("vnf-info")[0]

        # Set deployment name, vnfd, flavour id
        self.doc = Document()
        self.vnfInfo_ele.getElementsByTagName("name")[0].appendChild(self.doc.createTextNode(
            self.parsed_yaml["topology_template"]["node_templates"]["vnf"]["properties"]["product_name"] + "-vnf"))
        self.vnfInfo_ele.getElementsByTagName("description")[0].appendChild(self.doc.createTextNode(
            self.parsed_yaml["topology_template"]["node_templates"]["vnf"]["properties"]["product_name"] + "-vnf"))
        self.vnfInfo_ele.getElementsByTagName("vnfd")[0].appendChild(self.doc.createTextNode(
            self.parsed_yaml["topology_template"]["node_templates"]["vnf"]["properties"]["descriptor_id"]))
        self.vnfInfo_ele.getElementsByTagName("vnfd-flavour")[0].appendChild(self.doc.createTextNode(
            self.parsed_yaml["topology_template"]["node_templates"]["vnf"]["properties"]["flavour_id"]))
        self.add_vdu()
        self.add_virtual_link()
        self.add_vnfd_connection_points()
        self.add_inputs()
        self.output()

    def add_vnfd_connection_points(self):
        for extcp in self.parsed_yaml["topology_template"]["substitution_mappings"]["requirements"]:
            for k, v in extcp.items():
                vnfdcp_ele = self.doc.createElement("vnfd-connection-point")
                if "management" in self.parsed_yaml["topology_template"]["node_templates"][k]["properties"] and self.parsed_yaml["topology_template"]["node_templates"][k]["properties"]["management"] is True:
                    continue
                else:
                    idele = self.doc.createElement("id")
                    idele.appendChild(self.doc.createTextNode(k))
                    nwnameele = self.doc.createElement('network-name')
                    nwnameele.appendChild(self.doc.createTextNode(""))
                    subnetele = self.doc.createElement("subnets")
                    subnetname_ele = self.doc.createElement("subnet-name")
                    subnetname_ele.appendChild(self.doc.createTextNode(""))
                    subnetele.appendChild(subnetname_ele)
                    vnfdcp_ele.appendChild(idele)
                    vnfdcp_ele.appendChild(nwnameele)
                    vnfdcp_ele.appendChild(subnetele)
                    self.vnfInfo_ele.appendChild(vnfdcp_ele)

    def add_virtual_link(self):
        for vl in self.parsed_yaml["topology_template"]["node_templates"].keys():
            if self.parsed_yaml["topology_template"]["node_templates"][vl]["type"] == "tosca.nodes.nfv.VnfVirtualLink":
                vl_ele = self.create_virtual_link(vl)
                self.vnfInfo_ele.appendChild(vl_ele)

    def create_virtual_link(self,vl):
        vl_dom = parseString("""
                <virtual-link>
                    <id></id>
                    <is-externally-managed>true</is-externally-managed>
                    <network-name></network-name>
                </virtual-link>
            """)
        vl_ele = vl_dom.getElementsByTagName("virtual-link")[0]
        vl_id_ele = vl_ele.getElementsByTagName("id")[0]
        vl_id_ele.appendChild(self.doc.createTextNode(vl))
        return vl_ele

    def add_vdu(self):
        for k, v in self.parsed_yaml["topology_template"]["node_templates"].items():
            if self.parsed_yaml["topology_template"]["node_templates"][k]["type"] == "cisco.nodes.nfv.Vdu.Compute":
                vdu_ele = self.doc.createElement("vdu")
                id_ele = self.doc.createElement("id")
                id_ele.appendChild(self.doc.createTextNode(k))
                flavor_ele = self.doc.createElement("flavour-name")
                flavor_ele.appendChild(self.doc.createTextNode(""))
                vdu_ele.appendChild(id_ele)
                vdu_ele.appendChild(flavor_ele)
                vdu_ele.appendChild(self.add_resource_allocation())
                int_cps, ext_cps = self.get_connection_points(k)
                for int_cp in int_cps:
                    self.add_internal_cp(int_cp, vdu_ele)
                for ext_cp in ext_cps:
                    self.add_external_cp(ext_cp, vdu_ele)

                self.vnfInfo_ele.appendChild(vdu_ele)

    def get_connection_points(self, vdu_name):
        int_cps = []
        ext_cps = []
        node_template = self.parsed_yaml["topology_template"]["node_templates"]
        for k, v in node_template.items():
            if node_template[k]["type"] == "cisco.nodes.nfv.VduCp":
                if node_template[k]["requirements"][0]["virtual_binding"] and node_template[k]["requirements"][0]["virtual_binding"] == vdu_name:
                    if len(node_template[k]["requirements"]) > 1:
                        int_cps.append(k)
                    else:
                        ext_cps.append(k)
        return int_cps, ext_cps

    def add_internal_cp(self, int_cp, vdu_ele):
        log.info("Internal Cp Name : " + int_cp)
        icp = self.doc.createElement("internal-connection-point")
        id_ele = self.doc.createElement("id")
        id_ele.appendChild(self.doc.createTextNode(int_cp))
        icp.appendChild(id_ele)
        if "allowed_address_pairs" in self.parsed_yaml["topology_template"]["node_templates"][int_cp]["properties"]:
            addr_pair_dom = self.add_allowed_address_pair()
            addr_pair_ele = addr_pair_dom.getElementsByTagName("allowed-address-pair")[0]
            icp.appendChild(addr_pair_ele)
        vdu_ele.appendChild(icp)

    def add_external_cp(self, ext_cp, vdu_ele):
        log.info("External Cp Name : " + ext_cp)
        extcp = self.doc.createElement("internal-connection-point")
        id_ele = self.doc.createElement("id")
        id_ele.appendChild(self.doc.createTextNode(ext_cp))
        extcp.appendChild(id_ele)
        intcp_eleDom = parseString("""
                  <connection-point-address>
                     <sol3-parameters>
                        <ecp-connection>
                            <ip-address>
                                <id></id>
                                <type></type>
                                <subnet-name></subnet-name>
                                <fixed-address>
                                    <address></address>
                                </fixed-address>
                            </ip-address>
                        </ecp-connection>
                    </sol3-parameters>
                  </connection-point-address>  
            """)

        cp_ele = intcp_eleDom.getElementsByTagName("connection-point-address")[0]
        allow_addr_eleDom = self.add_allowed_address_pair()
        addr_pair_ele = allow_addr_eleDom.getElementsByTagName("allowed-address-pair")[0]
        cp_json = self.parsed_yaml["topology_template"]["node_templates"][ext_cp]
        ip_type = "IPV4"
        if cp_json["properties"]["protocol"][0]["associated_layer_protocol"] == "ipv6":
            ip_type = "IPV6"
        cp_ele.getElementsByTagName("sol3-parameters")[0].getElementsByTagName("ecp-connection")[
                0].getElementsByTagName("ip-address")[0].getElementsByTagName("type")[0].appendChild(
                self.doc.createTextNode(ip_type))


        # if cp_json["properties"]["order"]:
        #     log.debug(cp_json["properties"]["order"])
        #     cp_ele.getElementsByTagName("sol3-parameters")[0].getElementsByTagName("ecp-connection")[
        #         0].getElementsByTagName("ip-address")[0].getElementsByTagName("id")[0].appendChild(
        #         doc.createTextNode(str(cp_json["properties"]["order"])))
        # if vdujson["properties"].has_key("allowed_address_pairs"):
        #     addr_pair_ele.getElementsByTagName("address")[0].appendchild(doc.createTextNode(vdujson["properties"]["allowed_address_pairs"][0][]))

        extcp.appendChild(cp_ele)
        extcp.appendChild(addr_pair_ele)
        vdu_ele.appendChild(extcp)

    def add_allowed_address_pair(self):
        allow_addr_eleDom = parseString(
            """
                <allowed-address-pair>
                    <address></address>
                    <netmask></netmask>
                </allowed-address-pair>
            """)
        return allow_addr_eleDom

    def add_resource_allocation(self):
        ra_ele = self.doc.createElement("resource-allocation")
        vim_ele = self.doc.createElement("vim")
        vim_ele.appendChild(self.doc.createTextNode(self.args.vim))
        zone_ele = self.doc.createElement("zone-id")
        zone_ele.appendChild(self.doc.createTextNode(self.args.zone_id))
        ra_ele.appendChild(vim_ele)
        ra_ele.appendChild(zone_ele)
        return ra_ele

    def add_inputs(self):
        for paramId in self.parsed_yaml["topology_template"]["inputs"].keys():
            self.add_additional_parameter(paramId)

    def add_additional_parameter(self, paramId):
        doc = Document()
        paramNode = doc.createElement('additional-parameters')
        id = doc.createElement('id')
        id.appendChild(doc.createTextNode(paramId))
        paramNode.appendChild(id)
        attr_type = doc.createElement('type')
        attr_type.appendChild(doc.createTextNode("string"))
        paramNode.appendChild(attr_type)
        attr_value = doc.createElement('value')
        if paramId in self.sol003json["additionalParams"]:
            attr_value.appendChild(doc.createTextNode(str(self.sol003json["additionalParams"][paramId])))
        else:
            attr_value.appendChild(doc.createTextNode(""))
        paramNode.appendChild(attr_value)
        self.vnfInfo_ele.appendChild(paramNode)

    def output(self):
        if self.args.output:
            abs_path = os.path.abspath(self.args.output)
            abs_dir = os.path.dirname(abs_path)
            if not os.path.exists(abs_dir):
                os.makedirs(abs_dir, exist_ok=True)
            with open(self.args.output, 'w') as f:
                self.vnfInfodom.writexml(writer=f, encoding='UTF-8', newl='\n', addindent='\t')
        if not self.args.output:
            sys.stdout.write(self.vnfInfodom.toprettyxml())

def setup_logger(log_level=logging.INFO):
    log_format = "%(levelname)s - %(message)s"
    log_folder = "logs"
    log_filename = log_folder + "/yangtovnfinfo.log"
    # Ensure log folder exists
    if not os.path.exists(log_filename):
        os.mkdir(log_folder)

    logging.basicConfig(level=log_level, filename=log_filename, format=log_format)
    console = logging.StreamHandler()
    console.setLevel(log_level)
    console.setFormatter(logging.Formatter(log_format))
    logging.getLogger().addHandler(console)

if __name__ == "__main__":
    yangtovnfinfo()
