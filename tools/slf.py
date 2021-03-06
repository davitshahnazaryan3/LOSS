"""
user defines storey-loss function parameters
"""
import pandas as pd
import pickle
import numpy as np
import re
from scipy.interpolate import interp1d
import warnings
warnings.filterwarnings('ignore')


class SLF:
    def __init__(self, fileName, nstories, repl_cost=1., flag3d=True, normalize=False):
        """
        initialize storey loss function definition
        :param fileName: dict                       SLF data file
        :param nstories: int                        Number of stories
        :param repl_cost: float                     Replacement cost
        :param flag3d: bool                         3D or 2D modelling
        :param normalize: bool                      Normalize SLFs by replacement cost
        """
        self.fileName = fileName
        self.nstories = nstories
        self.repl_cost = repl_cost
        self.flag3d = flag3d
        self.normalize = normalize
        if str(fileName).endswith("xlsx"):
            # Not recommended
            self.flag = False
        else:
            self.flag = True

    def provided_slf(self):
        """
        provided as input SLF function
        :return df: DataFrame or dict               Storey loss functions in terms of ELR and EDP
        """
        filename = self.fileName
        if not self.flag:
            # NOTE: not recommended, very limited, option to be removed
            df = pd.read_excel(io=filename)
            y_ns_pfa_range = df['E_NS_PFA']
            y_s_psd_range = df['E_S_IDR']
            y_ns_psd_range = df['E_NS_IDR']
            
            # Normalization of storey loss functions
            max_slf = max(y_s_psd_range) + max(y_ns_psd_range) + max(y_ns_pfa_range)
            max_s_psd = max(y_s_psd_range) / max_slf
            max_ns_psd = max(y_ns_psd_range) / max_slf
            max_ns_pfa = max(y_ns_pfa_range) / max_slf
            
            # Story loss ratio weight (homogeneous along the height, no consideration given for PFA of ground and roof)
            storey_loss_ratio_weight = 1 / self.nstories
            
            # Normalized functions
            df["E_NS_PFA"] = df["E_NS_PFA"] * max_ns_pfa / max(y_ns_pfa_range) * storey_loss_ratio_weight
            df["E_NS_IDR"] = df["E_NS_IDR"] * max_ns_psd / max(y_ns_psd_range) * storey_loss_ratio_weight
            df["E_S_IDR"] = df["E_S_IDR"] * max_s_psd / max(y_s_psd_range) * storey_loss_ratio_weight
            
        else:
            # SLFs that accounts for the whole building inventory in a 3D space (unscaled)
            file = open(filename, "rb")
            df = pickle.load(file)
            file.close()

        return df
    
    def get_interpolation_functions(self, df):
        """
        Defines Interpolation functions for all SLFs
        Structure of SLF dictionary:
            Directional -> IDR_NS, IDR -> dir1, dir2 -> stories -> edp vs loss
            Non-directional -> IDR_S, IDR_NS, PFA_NS -> stories or floors -> edp vs loss
        :param df: DataFrame or dict                Storey loss functions in terms of ELR and EDP
        :return interpolation_functions: dict       Interpolation functions normalized by total building cost
        """
        interpolation_functions = {}
        if not self.flag:
            # TODO, add normalization for csv option
            # Not recommended, to be removed in future updates, or be updated not to be so underwhelming
            for key in df:
                if key.startswith("E_"):
                    slf_temp = np.array(df[key])
                    slf_temp = np.insert(slf_temp, 0, 0)
                    component_type = re.search('_(.*)_', key).group(1)
                    try:
                        edp_temp = np.array(df[f"{key[-3:]}_{component_type}"])
                    except:
                        edp_temp = np.array(df[f"{key[-3:]}"])
                    edp_temp = np.insert(edp_temp, 0, 0)
                    # Append into interpolation functions
                    interpolation_functions[f"{key[-3:]}_{component_type}"] = interp1d(edp_temp, slf_temp)
        else:
            # Normalize SLFs by the replacement cost
            # print(df["Non-directional"]["PFA_NS"]["0"]["loss"])
            total_comp_cost = 0
            for d in df:
                for key in df[d]:
                    if d == "Non-directional":
                        for i in df[d][key].keys():
                            total_comp_cost += max(df[d][key][i]["loss"])
                            # print(d, key, i, df[d][key][i]["loss"])
                    else:
                        if self.flag3d:
                            directions = ["dir1", "dir2"]
                        else:
                            # Does not consider costs associated with components sensitive along 2nd direction
                            directions = ["dir1"]
                        for x in directions:
                            for i in df[d][key][x]:
                                total_comp_cost += max(df[d][key][x][i]["loss"])

            if self.normalize:
                factor = self.repl_cost / total_comp_cost
            else:
                factor = 1.

            # Looping through directionality type
            for d in df:
                interpolation_functions[d] = {}
                # Looping through the EDP keys, generally, IDR_NS, IDR_S, PFA_NS
                for key in df[d]:
                    interpolation_functions[d][key] = {}
                    # Non-directional components (components sensitive to damage in all directions)
                    if d == "Non-directional":
                        # Loop for each floor or story
                        for i in df[d][key].keys():
                            edp_temp = np.insert(df[d][key][i]["edp"], 0, 0)
                            # Truncating the lower tail to zero to avoid negative costs
                            # (in case it was not done earlier)
                            df[d][key][i]["loss"][df[d][key][i]["loss"] < 0] = 0.0
                            
                            slf_temp = np.insert(df[d][key][i]["loss"], 0, 0)
                            interpolation_functions[d][key][int(i[-1])] = interp1d(edp_temp, slf_temp * factor)

                    # IDR-sensitive components
                    else:
                        # Loop for each direction, 1 and 2, x or y
                        for x in df[d][key].keys():
                            interpolation_functions[d][key][x] = {}
                            # Loop for each story
                            for i in df[d][key][x]:
                                edp_temp = np.insert(df[d][key][x][i]["edp"], 0, 0)
                                slf_temp = np.insert(df[d][key][x][i]["loss"], 0, 0)

                                interpolation_functions[d][key][x][int(i[-1])] = interp1d(edp_temp, slf_temp * factor)

        return interpolation_functions


if __name__ == "__main__":
    
    from pathlib import Path
    directory = Path.cwd()
#    name = "slf.xlsx"
    name = "slfs.pickle"
    slf = SLF(directory.parents[0] / "client" / name, 3)
    df = slf.provided_slf()
    int_func = slf.get_interpolation_functions(df)
