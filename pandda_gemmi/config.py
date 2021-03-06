from __future__ import annotations

import typing
import dataclasses

import argparse
from pathlib import Path

from pandda_gemmi.pandda_types import *


@dataclasses.dataclass()
class DatasetFlags:
    ground_state_datasets: typing.List[Dtag] = None
    exclude_from_z_map_analysis: typing.List[Dtag] = None
    exclude_from_characterisation: typing.List[Dtag] = None
    only_datasets: typing.List[Dtag] = None
    ignore_datasets: typing.List[Dtag] = None

    @classmethod
    def from_args(cls, args):
        return DatasetFlags(ground_state_datasets=[Dtag(dtag) for dtag in args.ground_state_datasets.split(",")],
                            exclude_from_z_map_analysis=[Dtag(dtag) for dtag
                                                         in args.exclude_from_z_map_analysis.split(",")],
                            exclude_from_characterisation=[Dtag(dtag) for dtag
                                                           in args.exclude_from_characterisation.split(",")],
                            only_datasets=[Dtag(dtag) for dtag in args.only_datasets.split(",")],
                            ignore_datasets=[Dtag(dtag) for dtag in args.ignore_datasets.split(",")],
                            )


@dataclasses.dataclass()
class Input:
    data_dirs: Path
    mtz_regex: str
    pdb_regex: str
    dataset_flags: DatasetFlags
    ligand_cif_regex: str
    ligand_pdb_regex: str

    @classmethod
    def from_args(cls, args):
        return Input(data_dirs=Path(args.data_dirs),
                     mtz_regex=args.mtz_regex,
                     pdb_regex=args.pdb_regex,
                     dataset_flags=DatasetFlags.from_args(args),
                     ligand_cif_regex=args.ligand_cif_regex,
                     ligand_pdb_regex=args.ligand_pdb_regex,
                     )


@dataclasses.dataclass()
class ResolutionBinning:
    dynamic_res_limits: bool = True
    high_res_upper_limit: float = 0.0
    high_res_lower_limit: float = 4.0
    high_res_increment: float = 0.05
    max_shell_datasets: int = 60
    min_characterisation_datasets: int = 60

    @classmethod
    def from_args(cls, args):
        return ResolutionBinning(dynamic_res_limits=args.dynamic_res_limits,
                                 high_res_upper_limit=args.high_res_upper_limit,
                                 high_res_lower_limit=args.high_res_lower_limit,
                                 high_res_increment=args.high_res_increment,
                                 max_shell_datasets=args.max_shell_datasets,
                                 min_characterisation_datasets=args.min_characterisation_datasets
                                 )


@dataclasses.dataclass()
class DiffractionData:
    structure_factors: StructureFactors = StructureFactors.from_string("FWT,PHWT")
    low_resolution_completeness: float = 4.0
    all_data_are_valid_values: bool = True
    sample_rate: float = 4.0

    @classmethod
    def from_args(cls, args):
        return DiffractionData(structure_factors=StructureFactors.from_string(args.structure_factors),
                               low_resolution_completeness=args.low_resolution_completeness,
                               all_data_are_valid_values=args.all_data_are_valid_values,
                               sample_rate=args.sample_rate,
                               )


@dataclasses.dataclass()
class Filtering:
    max_rfree: float = 0.4
    max_rmsd_to_reference: float = 1.5
    max_wilson_plot_z_score: float = 5.0
    same_space_group_only: bool = True
    similar_models_only: bool = False

    @classmethod
    def from_args(cls, args):
        return Filtering(max_rfree=args.max_rfree,
                         max_rmsd_to_reference=args.max_rmsd_to_reference,
                         max_wilson_plot_z_score=args.max_wilson_plot_z_score,
                         same_space_group_only=args.same_space_group_only,
                         similar_models_only=args.similar_models_only,
                         )


@dataclasses.dataclass()
class BlobFinding:
    min_blob_volume: float
    min_blob_z_peak: float 
    # clustering_cutoff: float = 1.732
    clustering_cutoff: float 
    cluster_cutoff_distance_multiplier: float

    @classmethod
    def from_args(cls, args):
        return BlobFinding(min_blob_volume=args.min_blob_volume,
                           min_blob_z_peak=args.min_blob_z_peak,
                           clustering_cutoff=args.clustering_cutoff,
                           cluster_cutoff_distance_multiplier=args.cluster_cutoff_distance_multiplier,
                           )


@dataclasses.dataclass()
class BackgroundCorrection:
    min_bdc: float = 0.0
    max_bdc: float = 1.0
    increment: float = 0.01
    output_multiplier: float = 1.0

    @classmethod
    def from_args(cls, args):
        return BackgroundCorrection(min_bdc=args.min_bdc,
                                    max_bdc=args.max_bdc,
                                    increment=args.increment,
                                    output_multiplier=args.output_multiplier,
                                    )


@dataclasses.dataclass()
class Processing:
    process_dict_n_cpus: int = 12
    process_shells: str = "luigi"
    h_vmem: float = 100
    m_mem_free: float = 5

    @classmethod
    def from_args(cls, args):
        return Processing(process_dict_n_cpus=args.process_dict_n_cpus,
                          process_shells=args.process_shells,
                          h_vmem=args.h_vmem,
                          m_mem_free=args.m_mem_free,
                          )


@dataclasses.dataclass()
class MapProcessing:
    resolution_factor: float = 0.25
    grid_spacing: float = 0.5
    padding: float = 3
    density_scaling: str = "sigma"

    @classmethod
    def from_args(cls, args):
        return MapProcessing(resolution_factor=args.resolution_factor,
                             grid_spacing=args.grid_spacing,
                             padding=args.padding,
                             density_scaling=args.density_scaling,
                             )


@dataclasses.dataclass()
class Masks:
    outer_mask: float = 6
    inner_mask: float = 1.8
    inner_mask_symmetry: float = 3.0
    contour_level: float = 2.5
    negative_values: bool = False

    @classmethod
    def from_args(cls, args):
        return Masks(outer_mask=args.outer_mask,
                     inner_mask=args.inner_mask,
                     inner_mask_symmetry=args.inner_mask_symmetry,
                     contour_level=args.contour_level,
                     negative_values=args.negative_values,
                     )


@dataclasses.dataclass()
class Params:
    resolution_binning: ResolutionBinning
    diffraction_data: DiffractionData
    filtering: Filtering
    map_processing: MapProcessing
    masks: Masks
    blob_finding: BlobFinding
    background_correction: BackgroundCorrection
    processing: Processing

    @classmethod
    def from_args(cls, args):
        return cls(resolution_binning=ResolutionBinning.from_args(args),
                   diffraction_data=DiffractionData.from_args(args),
                   filtering=Filtering.from_args(args),
                   masks=Masks.from_args(args),
                   map_processing=MapProcessing.from_args(args),
                   blob_finding=BlobFinding.from_args(args),
                   background_correction=BackgroundCorrection.from_args(args),
                   processing=Processing.from_args(args),
                   )


@dataclasses.dataclass()
class Output:
    out_dir: Path

    @classmethod
    def from_args(cls, args):
        return cls(out_dir=Path(args.out_dir))


@dataclasses.dataclass()
class Config:
    input: Input
    output: Output
    params: Params
    debug: int

    @staticmethod
    def get_parser():
        parser = argparse.ArgumentParser()

        # Input
        parser.add_argument("--data_dirs",
                            type=str,
                            help="The directory for output and intermediate files to be saved to",
                            required=True
                            )
        parser.add_argument("--pdb_regex",
                            type=str,
                            help="The directory for output and intermediate files to be saved to",
                            required=True
                            )
        parser.add_argument("--mtz_regex",
                            type=str,
                            help="The directory for output and intermediate files to be saved to",
                            required=True
                            )
        parser.add_argument("--ligand_cif_regex",
                            type=str,
                            help="The directory for output and intermediate files to be saved to",
                            default="*.cif",
                            )
        parser.add_argument("--ligand_pdb_regex",
                            type=str,
                            help="The directory for output and intermediate files to be saved to",
                            default="abcdefg",
                            )
        # Dataset selection
        parser.add_argument("--ground_state_datasets",
                            default="",
                            type=str,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--exclude_from_z_map_analysis",
                            default="",
                            type=str,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--exclude_from_characterisation",
                            default="",
                            type=str,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--only_datasets",
                            default="",
                            type=str,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--ignore_datasets",
                            default="",
                            type=str,
                            help="The directory for output and intermediate files to be saved to",
                            )

        # Output
        parser.add_argument("--out_dir",
                            type=str,
                            help="The directory for output and intermediate files to be saved to",
                            required=True,
                            )

        # params
        # Res limits
        parser.add_argument("--dynamic_res_limits",
                            default=True,
                            type=bool,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--high_res_upper_limit",
                            default=0.0,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--high_res_lower_limit",
                            default=4.0,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--high_res_increment",
                            default=0.05,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--max_shell_datasets",
                            default=60,
                            type=int,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--min_characterisation_datasets",
                            default=60,
                            type=int,
                            help="The directory for output and intermediate files to be saved to",
                            )

        # Diffraction data
        parser.add_argument("--structure_factors",
                            default="FWT,PHWT",
                            type=str,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--all_data_are_valid_values",
                            default=True,
                            type=bool,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--low_resolution_completeness",
                            default=4.0,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--sample_rate",
                            default=4.0,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )

        # Filters
        parser.add_argument("--max_rmsd_to_reference",
                            default=1.5,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--max_rfree",
                            default=0.4,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--max_wilson_plot_z_score",
                            default=5.0,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--same_space_group_only",
                            default=True,
                            type=bool,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--similar_models_only",
                            default=False,
                            type=bool,
                            help="The directory for output and intermediate files to be saved to",
                            )

        # Maps
        parser.add_argument("--resolution_factor",
                            default=0.25,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--grid_spacing",
                            default=0.5,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--padding",
                            default=3,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--density_scaling",
                            default="sigma",
                            type=str,
                            help="The directory for output and intermediate files to be saved to",
                            )

        # masks
        parser.add_argument("--outer_mask",
                            default=6.0,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--inner_mask",
                            default=1.8,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--inner_mask_symmetry",
                            default=3.0,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--contour_level",
                            default=2.5,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--negative_values",
                            default=False,
                            type=bool,
                            help="The directory for output and intermediate files to be saved to",
                            )

        # blob finding
        parser.add_argument("--min_blob_volume",
                            default=8.0,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--min_blob_z_peak",
                            default=3.0,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--clustering_cutoff",
                            # default=1.732,
                            default=1.0,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--cluster_cutoff_distance_multiplier",
                    default=1.1,
                    type=float,
                    help="The directory for output and intermediate files to be saved to",
                    )
        

        # background correction
        parser.add_argument("--min_bdc",
                            default=0.0,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--max_bdc",
                            default=1.0,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--increment",
                            default=0.01,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--output_multiplier",
                            default=1.0,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )

        # processing
        parser.add_argument("--process_dict_n_cpus",
                            default=12,
                            type=int,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--process_shells",
                            default="luigi",
                            type=str,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--h_vmem",
                            default=100,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )
        parser.add_argument("--m_mem_free",
                            default=5,
                            type=float,
                            help="The directory for output and intermediate files to be saved to",
                            )

        # Debug

        parser.add_argument("--debug",
                            default=0,
                            type=int,
                            help="The directory for output and intermediate files to be saved to",
                            )

        return parser

    @staticmethod
    def from_args():
        parser = Config.get_parser()

        args = parser.parse_args()

        input: Input = Input.from_args(args)
        output: Output = Output.from_args(args)
        params: Params = Params.from_args(args)
        debug: int = int(args.debug)

        return Config(input=input,
                      output=output,
                      params=params,
                      debug=debug,
                      )

    @staticmethod
    def from_args_list(args_list):
        parser = Config.get_parser()

        args = parser.parse_args(args_list)

        input: Input = Input.from_args(args)
        output: Output = Output.from_args(args)
        params: Params = Params.from_args(args)
        debug: int = int(args.debug)


        return Config(input=input,
                      output=output,
                      params=params,
                      debug=debug,
                      )
