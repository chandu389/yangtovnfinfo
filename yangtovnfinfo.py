import sys
from xml.dom.minidom import parse,Document
import os
import logging
import argparse
import pyang
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
        parser.add_argument('-p', '--prune', action='store_false',
                            help='Do not prune empty values from the dict')
        parser.add_argument('-e', '--output-silent', action='store_true', default=False,
                            help=argparse.SUPPRESS)

        args = parser.parse_args()

        self.args = args
        self.parser = parser

        if not args.yangfile or not args.templatefile or not args.grouping:
            print("error: the following arguments are required: -yf/--yangfile, -tf/--templatefile, "
                  "-g/--grouping")
            return

        # Initialize the log and have the level set properly
        setup_logger(args.log_level)

        if not os.path.exists("tmp"):
            os.makedirs("tmp")
        os.system("pyang -f yin "+self.args.yangfile+" > ./tmp/yang.xml")
        self.yangdom = parse("./tmp/yang.xml")
        self.vnfInfodom = parse(self.args.templatefile)
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

    def add_additional_parameter(self,group):
        doc = Document()
        vnfInfo = self.vnfInfodom.getElementsByTagName("vnf-info")[0]
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
            vnfInfo.appendChild(paramNode)

    def find_grouping(self, groupName):
        for group in self.yangdom.getElementsByTagName("grouping"):
            if (group.getAttribute("name") == groupName):
                return group

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
