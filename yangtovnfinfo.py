import sys
from xml.dom.minidom import parse,Document,parseString
import os
import logging
import argparse
import yaml
log = logging.getLogger(__name__)

class yangtovnfinfo:
    def __init__(self, internal_run=False, internal_args=None):
        self.variables = None
        self.tosca_lines = None
        self.tosca_vnf = None
        self.converter = None
        self.provider = None
        self.supported_providers = None
        self.cnfv = None

        if internal_args and internal_args["e"] is False:
            print("Starting SolCon (v{})...".format(__version__))

        self.desc = "Yang model to SOL6 Vnf Info Converter XML"

        parser = argparse.ArgumentParser(description=self.desc)
        parser.add_argument('-sf', '--sol001file',
                            help="The sol001 yaml file to be processed")
        parser.add_argument('-yf', '--yangfile',
                            help="The yang file to be processed")
        parser.add_argument('-tf', '--templatefile',
                            help="The sample vnf-info template file to be processed")
        parser.add_argument('-g', '--grouping',
                            help="The yang group for extensions")
        parser.add_argument('-r', '--run',
                            help="Run time dir for ncs")
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
        parser.add_argument('-p', '--prune', action='store_false',
                            help='Do not prune empty values from the dict')
        parser.add_argument('-e', '--output-silent', action='store_true', default=False,
                            help=argparse.SUPPRESS)

        args = parser.parse_args()

        self.args = args
        self.parser = parser

        if not args.sol001file or not args.yangfile or not args.templatefile or not args.grouping:
            print("error: the following arguments are required: -sf/--sol001file, -yf/--yangfile, -tf/--templatefile, "
                  "-g/--grouping")
            return

        # Initialize the log and have the level set properly
        setup_logger(args.log_level)

        if not os.path.exists("tmp"):
            os.makedirs("tmp")
        os.system("pyang -f yin "+self.args.yangfile+" > ./tmp/yang.xml")
        self.yangdom = parse("./tmp/yang.xml")
        self.vnfInfodom = parse(self.args.templatefile)
        self.parsed_yaml = self.read_yaml(self.args.sol001file)
        self.vnfInfo_ele = self.vnfInfodom.getElementsByTagName("vnf-info")[0]
        self.ra_ele = self.add_resource_allocation()
        self.add_vdu()
        self.add_vnfd_connection_points()
        groupDom = self.find_grouping(self.args.grouping)
        if (groupDom):
            for usesgroup in groupDom.getElementsByTagName("uses"):
                name = usesgroup.getAttribute("name")
                usesgroupdom = self.find_grouping(name)
                if (usesgroupdom):
                    self.add_additional_parameter(usesgroupdom)
            self.add_additional_parameter(groupDom)


        self.vnf_info_sol6 = self.vnfInfodom.toprettyxml(indent="    ", newl="\n")
        self.output()

    def add_vnfd_connection_points(self):
        doc = Document()
        for extcp in self.parsed_yaml["topology_template"]["substitution_mappings"]["requirements"]:
            for k,v in extcp.items():
                vnfdcp_ele = doc.createElement("vnfd-connection-point")
                idele = doc.createElement("id")
                idele.appendChild(doc.createTextNode(k))
                nwnameele = doc.createElement('network-name')
                nwnameele.appendChild(doc.createTextNode(""))
                subnetele = doc.createElement("subnets")
                subnetname_ele = doc.createElement("subnet-name")
                subnetname_ele.appendChild(doc.createTextNode(""))
                subnetele.appendChild(subnetname_ele)
                vnfdcp_ele.appendChild(idele)
                vnfdcp_ele.appendChild(nwnameele)
                vnfdcp_ele.appendChild(subnetele)
                self.vnfInfo_ele.appendChild(vnfdcp_ele)

    def add_vdu(self):
        doc = Document()
        for k, v in self.parsed_yaml["topology_template"]["node_templates"].items():
            if self.parsed_yaml["topology_template"]["node_templates"][k]["type"] == "cisco.nodes.nfv.Vdu.Compute":
                vdu_ele = doc.createElement("vdu")
                id_ele = doc.createElement("id")
                id_ele.appendChild(doc.createTextNode(k))
                flavor_ele = doc.createElement("flavour-name")
                flavor_ele.appendChild(doc.createTextNode(""))
                vdu_ele.appendChild(id_ele)
                vdu_ele.appendChild(flavor_ele)
                vdu_ele.appendChild(self.ra_ele)
                int_cps, ext_cps = self.get_connection_points(k)
                for int_cp in int_cps:
                    self.add_internal_cp(int_cp,vdu_ele)
                for ext_cp in ext_cps:
                    self.add_external_cp(ext_cp,vdu_ele)

                self.vnfInfo_ele.appendChild(vdu_ele)

    def add_resource_allocation(self):
        doc = Document()
        ra_ele = doc.createElement("resource-allocation")
        vim_ele = doc.createElement("vim")
        vim_ele.appendChild(doc.createTextNode(self.args.vim))
        zone_ele = doc.createElement("zone-id")
        zone_ele.appendChild(doc.createTextNode(self.args.zone_id))
        ra_ele.appendChild(vim_ele)
        ra_ele.appendChild(zone_ele)
        return ra_ele

    def get_connection_points(self,vdu_name):
        int_cps = []
        ext_cps = []
        node_template = self.parsed_yaml["topology_template"]["node_templates"]
        for k, v in node_template.items():
            if node_template[k]["type"] == "cisco.nodes.nfv.VduCp":
                if node_template[k]["requirements"][0]["virtual_binding"] and node_template[k]["requirements"][0]["virtual_binding"] == vdu_name:
                    if len(node_template[k]["requirements"]) > 1:
                        int_cps.append(k)
                    else :
                        ext_cps.append(k)
        return int_cps,ext_cps

    def add_internal_cp(self,int_cp, vdu_ele):
        doc = Document()
        icp = doc.createElement("internal-connection-point")
        id_ele = doc.createElement("id")
        id_ele.appendChild(doc.createTextNode(int_cp))
        icp.appendChild(id_ele)
        vdu_ele.appendChild(icp)

    def add_external_cp(self,ext_cp,vdu_ele):
        doc = Document()
        extcp = doc.createElement("internal-connection-point")
        id_ele = doc.createElement("id")
        id_ele.appendChild(doc.createTextNode(ext_cp))
        extcp.appendChild(id_ele)
        cp_ele = parseString("<connection-point-address><sol3-parameters><ecp-connection><ip-address><id></id><type></type><subnet-name></subnet-name><fixed-address><address></address></fixed-address></ip-address></ecp-connection></sol3-parameters></connection-point-address>")
        extcp.appendChild(cp_ele.getElementsByTagName("connection-point-address")[0])
        vdu_ele.appendChild(extcp)


    def add_additional_parameter(self,group):
        doc = Document()
        for leaf in group.getElementsByTagName("leaf"):
            paramId = leaf.getAttribute("name")
            paramNode = doc.createElement('additional-parameters')
            id = doc.createElement('id')
            id.appendChild(doc.createTextNode(paramId))
            paramNode.appendChild(id)
            attr_value = doc.createElement('value')
            attr_value.appendChild(doc.createTextNode(""))
            paramNode.appendChild(attr_value)
            attr_type = doc.createElement('type')
            attr_type.appendChild(doc.createTextNode("string"))
            paramNode.appendChild(attr_type)
            self.vnfInfo_ele.appendChild(paramNode)

    def find_grouping(self, groupName):
        for group in self.yangdom.getElementsByTagName("grouping"):
            if (group.getAttribute("name") == groupName):
                return group

    def read_yaml(self, file):
        log.info("Reading YAML file {}".format(file))
        f = open(file, 'rb')
        file_read = f.read()
        f.close()
        parsed_yaml = yaml.safe_load(file_read)

        return parsed_yaml

    def output(self):
        # Get the absolute path, since apparently relative paths sometimes have issues with things?
        if self.args.output:
            abs_path = os.path.abspath(self.args.output)
            # Also python has a function for what I was sloppily doing, so use that
            abs_dir = os.path.dirname(abs_path)
            if not os.path.exists(abs_dir):
                os.makedirs(abs_dir, exist_ok=True)

            with open(self.args.output, 'w') as f:
                f.writelines(self.vnf_info_sol6)

        if not self.args.output and not self.args.output_silent:
            sys.stdout.write(self.vnf_info_sol6)

def setup_logger(log_level=logging.INFO):
    log_format = "%(levelname)s - %(message)s"
    log_folder = "logs"
    log_filename = log_folder + "/yangtovnfinfo.log"
    # Ensure log folder exists
    if not os.path.exists(log_filename):
        os.mkdir(log_folder)

    logging.basicConfig(level=log_level, filename=log_filename, format=log_format)
    # Duplicate the output to the console as well as to a file
    console = logging.StreamHandler()
    console.setLevel(log_level)
    console.setFormatter(logging.Formatter(log_format))
    logging.getLogger().addHandler(console)

if __name__ == "__main__":
    yangtovnfinfo()
