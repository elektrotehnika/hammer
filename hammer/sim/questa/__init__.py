#  Questa hammer-vlsi sim plugin

from hammer.vlsi import HammerSimTool, DummyHammerTool, HammerToolStep, deepdict
from hammer.config import HammerJSONEncoder

import hammer.tech as hammer_tech
from hammer.tech import HammerTechnologyUtils # used for get_verilog_models

from typing import Dict, List, Any, Optional
from decimal import Decimal

import os
import json


class questa(HammerSimTool, DummyHammerTool):

    # @property
    # def env_vars(self) -> Dict[str, str]:
    #     new_dict = deepdict(super().env_vars)
    #     new_dict.update({})
    #     return new_dict

    # Simulation steps
    @property
    def steps(self) -> List[HammerToolStep]:
        return self.make_steps_from_methods([
            self.qhsim
        ])

    # @property
    # def force_regs_file_path(self) -> str:
    #     return os.path.join(self.run_dir, "{module}_regs.txt".format(module=self.top_module))

    # Main simulation method
    def qhsim(self) -> bool:
        # Get Hammer settings
        tb_name = self.get_setting("sim.inputs.tb_name")
        tb_dut = self.get_setting("sim.inputs.tb_dut")
        defines = self.get_setting("sim.inputs.defines")
        timescale = self.get_setting("sim.inputs.timescale")
        input_files_list = self.get_setting("sim.inputs.input_files")
        top_module = self.get_setting("sim.inputs.top_module")
        level = self.get_setting("sim.inputs.level")
        timing_annotated = self.get_setting("sim.inputs.timing_annotated")
        questa_bin = self.get_setting("sim.questa.questa_bin")
        # Create a Questa command file
        do_file = f"{self.run_dir}/{tb_name}.do"
        f = open(do_file,"w+")
        # Create the working library
        lib_name = f"work_{tb_name}"
        lib_dir = f"{self.run_dir}/{lib_name}"
        f.write("# Create the working library\n")
        f.write(f"rm -rf {lib_dir}\n")
        f.write(f"vlib {lib_dir}\n")
        f.write(f"vmap {lib_name} {lib_dir}\n") # potentially redundant
        # Compile the design units
        defines_list = [f"+define+{x}" for x in defines]
        defines_string = " ".join(defines_list)
        for i in range(len(input_files_list)):
            if (input_files_list[i][0] != '/'):
                input_files_list[i] = os.getcwd() + '/' + input_files_list[i]
        input_files_string = " ".join(input_files_list)
        if level in ["syn", "par"]:
            verilog_models_list = self.get_verilog_models()
            verilog_models_string = " ".join(verilog_models_list)
            input_files_string += ' ' + verilog_models_string
            print (input_files_string)
        f.write("# Compile the design units\n")
        f.write("# Suppressing the vlog-2892 error in Verilog models of library cells\n")
        f.write("# - (vlog-2892) Net type of 'NET_NAME' was not explicitly declared.\n")
        f.write(f"vlog -suppress 2892 -work {lib_name} {defines_string} -timescale {timescale} {input_files_string}\n")
        # Optimize the design
        sdf_args = "-nosdf +notimingchecks"
        if timing_annotated:
            sdf_corner = self.get_setting("sim.inputs.sdf_corner")
            if not self.sdf_file: # if SDF file not specified in input .yml
                if level == "par":
                    sdf_file = f"{self.run_dir}/../par-rundir/{top_module}.par.sdf.gz"
                elif level == "syn":
                    sdf_file = f"{self.run_dir}/../syn-rundir/{top_module}.mapped.sdf"
            else:
                sdf_file = self.sdf_file if self.sdf_file[0] == '/' else os.getcwd() + '/' + self.sdf_file
            sdf_args = f" +sdf_verbose -sdf{sdf_corner} /{tb_name}/{tb_dut}={sdf_file}"
        f.write("# Optimize the design\n")
        f.write("# +acc provides visibility for debugging purposes\n")
        f.write("# -o provides the name of the optimized design file name\n")
        f.write(f"vopt -work {lib_name} -timescale {timescale} {sdf_args} +acc {tb_name} -o opt_{tb_name}\n")
        # Load the design
        f.write("# Load the design\n")
        f.write(f"vsim  -work {lib_name} opt_{tb_name}\n")
        # Add waves
        f.write("# Add waves\n")
        f.write("add wave -r *\n")
        # Log simulation data
        f.write("# Log simulation data\n")
        f.write("log -r *\n") # potentially redundant
        # Run simulation (if enabled)
        if self.get_setting("sim.inputs.execute_sim"):
            f.write("# Run simulation\n")
            f.write("run -all\n")
        else:
            self.logger.warning("Not running any simulations because sim.inputs.execute_sim is unset.")
        # Close the Questa command file
        f.close()
        # Run Questa simulation
        args = [questa_bin]
        args.append("-do")
        args.append(f"{do_file}")
        self.run_executable(args, cwd=self.run_dir)
        return True

    # Fill output json file
    def fill_outputs(self) -> bool:
        self.output_waveforms = []
        self.output_saifs = []
        self.output_top_module = self.top_module
        self.output_tb_name = self.get_setting("sim.inputs.tb_name")
        self.output_tb_dut = self.get_setting("sim.inputs.tb_dut")
        self.output_level = self.get_setting("sim.inputs.level")
        return True

    # Get verilog models of standard cells
    def get_verilog_models(self) -> List[str]:
        verilog_sim_files = self.technology.read_libs([hammer_tech.filters.verilog_sim_filter],
                                                      hammer_tech.HammerTechnologyUtils.to_plain_item)
        return verilog_sim_files


    def tool_config_prefix(self) -> str:
        return "sim.questa"


tool = questa
