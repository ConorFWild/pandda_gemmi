from __future__ import annotations

import typing
import dataclasses

import re
from pathlib import Path

import numpy as np
import scipy
from scipy import spatial
import pandas as pd
import gemmi

from pandda_gemmi.constants import *
from pandda_gemmi.config import *


@dataclasses.dataclass()
class Dtag:
    dtag: str

    def __hash__(self):
        return hash(self.dtag)


@dataclasses.dataclass()
class EventIDX:
    event_idx: int

    def __hash__(self):
        return hash(self.event_idx)


@dataclasses.dataclass()
class ResidueID:
    model: str
    chain: str
    insertion: str

    @staticmethod
    def from_residue_chain(model: gemmi.Model, chain: gemmi.Chain, res: gemmi.Residue):
        return ResidueID(model.name,
                         chain.name,
                         str(res.seqid.num),
                         )

    def __hash__(self):
        return hash((self.model, self.chain, self.insertion))


@dataclasses.dataclass()
class RFree:
    rfree: float

    @staticmethod
    def from_structure(structure: Structure):
        print(list(structure.structure.make_mmcif_document()[0].find_loop("_refine.ls_R_factor_R_free"))[0])
        rfree = structure.structure.make_mmcif_document()[0].find_loop("_refine.ls_R_factor_R_free")[0]
        # print([[item for item in x] for x in structure.structure.make_mmcif_document()])

        # regex = "REMARK   3   FREE R VALUE                     :  ([^\s]+))"
        # matches = re.findall(regex,
        #                      string,
        #                      )
        #
        # rfree = float(matches[0])

        return RFree(float(rfree))

    def to_float(self):
        return self.rfree


@dataclasses.dataclass()
class Structure:
    structure: gemmi.Structure

    @staticmethod
    def from_file(file: Path) -> Structure:
        structure = gemmi.read_structure(str(file))
        return Structure(structure)

    def rfree(self):
        return RFree.from_structure(self)

    def __getitem__(self, item: ResidueID):
        return self.structure[item.model][item.chain][item.insertion]

    def residue_ids(self):
        residue_ids = []
        for model in self.structure:
            for chain in model:
                for residue in chain.get_polymer():
                    resid = ResidueID.from_residue_chain(model, chain, residue)
                    residue_ids.append(resid)

        return residue_ids


@dataclasses.dataclass()
class StructureFactors:
    f: str
    phi: str

    @staticmethod
    def from_string(string: str):
        factors = string.split(",")
        assert len(factors) == 2
        return StructureFactors(f=factors[0],
                                phi=factors[1],
                                )


@dataclasses.dataclass()
class Reflections:
    reflections: gemmi.MTZ

    @staticmethod
    def from_file(file: Path) -> Reflections:
        reflections = gemmi.read_mtz_file(str(file))
        return Reflections(reflections)

    def resolution(self) -> Resolution:
        return Resolution.from_float(self.reflections.resolution_high())

    def truncate(self, resolution: Resolution):
        new_reflections = gemmi.MTZ()

        # Set dataset properties
        new_reflections.spacegroup = self.reflections.spacegroup
        new_reflections.set_cell_for_all(self.reflections.unit_cell)

        # Add dataset
        new_reflections.add_dataset("truncated")

        # Add columns
        for column in self.reflections.columns:
            new_reflections.add_column(column.label, column.type)

        # Update data
        old_data = np.array(self.reflections, copy=True)
        new_reflections.set_data(old_data[self.reflections.make_d_array() >= resolution.resolution])

        # Update resolution
        new_reflections.update_reso()

    def spacegroup(self):
        return self.reflections.spacegroup

    def columns(self):
        return self.reflections.column_labels()

    def missing(self, structure_factors: StructureFactors, resolution: Resolution) -> pd.DataFrame:
        all_data = np.array(self.reflections, copy=False)
        resolution_array = self.reflections.make_d_array()

        table = pd.DataFrame(data=all_data, columns=self.reflections.column_labels())

        reflections_in_resolution = table[resolution_array >= resolution.to_float()]

        amplitudes = reflections_in_resolution[structure_factors.f]

        missing = reflections_in_resolution[amplitudes == 0]

        return missing


@dataclasses.dataclass()
class Dataset:
    structure: Structure
    reflections: Reflections

    @staticmethod
    def from_files(pdb_file: Path, mtz_file: Path):
        strucure: Structure = Structure.from_file(pdb_file)
        reflections: Reflections = Reflections.from_file(mtz_file)

        return Dataset(structure=strucure,
                       reflections=reflections,
                       )


@dataclasses.dataclass()
class Datasets:
    datasets: typing.Dict[Dtag, Dataset]

    @staticmethod
    def from_dir(pandda_fs_model: PanDDAFSModel):
        datasets = {}
        for dtag, dataset_dir in pandda_fs_model.data_dirs.to_dict().items():
            dataset: Dataset = Dataset.from_files(dataset_dir.input_pdb_file,
                                                  dataset_dir.input_mtz_file,
                                                  )

            datasets[dtag] = dataset

        return Datasets(datasets)

    def __getitem__(self, item):
        return self.datasets[item]

    def remove_dissimilar_models(self, reference: Reference, max_rmsd_to_reference: float) -> Datasets:
        print(max_rmsd_to_reference)

        new_dtags = filter(lambda dtag: (RMSD.from_structures(self.datasets[dtag].structure,
                                                              reference.structure,
                                                              )).to_float() < max_rmsd_to_reference,
                           self.datasets,
                           )

        new_datasets = {dtag: self.datasets[dtag] for dtag in new_dtags}

        return Datasets(new_datasets)

    def remove_invalid_structure_factor_datasets(self,
                                                 structure_factors: StructureFactors,
                                                 ) -> Datasets:
        new_dtags = filter(lambda dtag: (structure_factors.f in self.datasets[dtag].reflections.columns()) and (
                structure_factors.phi in self.datasets[dtag].reflections.columns()),
                           self.datasets,
                           )

        new_datasets = {dtag: self.datasets[dtag] for dtag in new_dtags}

        return Datasets(new_datasets)

    def remove_incomplete_up_to_resolution_datasets(self, structure_factors, resolution: Resolution):
        no_missing_reflections_dtags = filter(
            lambda dtag: len(self.datasets[dtag].reflections.missing(structure_factors.f,
                                                                     resolution=resolution,
                                                                     )
                             ) > 0,
            self.datasets,
        )

        new_datasets = {dtag: self.datasets[dtag] for dtag in no_missing_reflections_dtags}

        return Datasets(new_datasets)

    def remove_low_resolution_datasets(self, resolution_cutoff):
        high_resolution_dtags = filter(
            lambda dtag: self.datasets[dtag].reflections.resolution().to_float() < resolution_cutoff,
            self.datasets,
        )

        new_datasets = {dtag: self.datasets[dtag] for dtag in high_resolution_dtags}

        return Datasets(new_datasets)

    def scale_reflections(self):
        # Scale to the reference dataset
        return self

    def remove_bad_rfree(self, max_rfree: float):
        good_rfree_dtags = filter(
            lambda dtag: self.datasets[dtag].structure.rfree().to_float() < max_rfree,
            self.datasets,
        )

        new_datasets = {dtag: self.datasets[dtag] for dtag in good_rfree_dtags}

        return Datasets(new_datasets)

    def remove_dissimilar_space_groups(self, reference: Reference):
        same_spacegroup_datasets = filter(
            lambda dtag: self.datasets[dtag].reflections.spacegroup() == reference.reflections.spacegroup(),
            self.datasets,
        )

        new_datasets = {dtag: self.datasets[dtag] for dtag in same_spacegroup_datasets}

        return Datasets(new_datasets)

    def remove_bad_wilson(self, max_wilson_plot_z_score: float):
        return self

    def truncate(self, resolution):
        pass

    def __iter__(self):
        for dtag in self.datasets:
            yield dtag


@dataclasses.dataclass()
class Reference:
    structure: Structure
    reflections: Reflections

    @staticmethod
    def from_datasets(datasets: Datasets):
        resolutions: typing.Dict[Dtag, Resolution] = {}
        for dtag in datasets:
            resolutions[dtag] = datasets[dtag].reflections.resolution()

        min_resolution_dtag = min(resolutions,
                                  key=lambda dtag: resolutions[dtag].to_float(),
                                  )

        min_resolution_structure = datasets[min_resolution_dtag].structure
        min_resolution_reflections = datasets[min_resolution_dtag].reflections

        return Reference(min_resolution_structure,
                         min_resolution_reflections,
                         )


@dataclasses.dataclass()
class Partitioning:
    partitioning: typing.Dict[ResidueID, typing.Dict[typing.Tuple[int], gemmi.Position]]

    def __getitem__(self, item: ResidueID):
        return self.partitioning[item]

    @staticmethod
    def from_reference(reference: Reference,
                       grid: gemmi.FloatGrid,
                       ):

        array = np.array(grid, copy=False)

        spacing = np.array([grid.nu, grid.nv, grid.nw])

        poss = []
        res_indexes = {}
        i = 0
        for model in reference.structure.structure:
            for chain in model:
                for res in chain.get_polymer():
                    ca = res["CA"][0]

                    position = ca.pos

                    fractional = grid.unit_cell.fractionalize(position)

                    poss.append(fractional)

                    res_indexes[i] = ResidueID.from_residue_chain(model, chain, res)
                    i = i + 1

        ca_position_array = np.array([[x for x in pos] for pos in poss])

        kdtree = spatial.KDTree(ca_position_array)

        coord_array = [coord for coord, val in np.ndenumerate(array)]

        query_points = np.array([[x / spacing[i] for i, x in enumerate(coord)] for coord in coord_array])

        distances, indexes = kdtree.query(query_points)

        partitions = {}
        for i, coord in enumerate(coord_array):
            res_num = indexes[i]

            res_id = res_indexes[res_num]

            if res_id not in partitions:
                partitions[res_id] = {}

            partitions[res_id][coord] = grid.unit_cell.orthogonalize(gemmi.Fractional(coord[0] / spacing[0],
                                                                                      coord[1] / spacing[1],
                                                                                      coord[2] / spacing[2],
                                                                                      )
                                                                     )

        return Partitioning(partitions)


@dataclasses.dataclass()
class Grid:
    grid: gemmi.FloatGrid
    partitioning: Partitioning

    @staticmethod
    def from_reference(reference: Reference):
        unit_cell = Grid.unit_cell_from_reference(reference)
        spacing: typing.List[int] = Grid.spacing_from_reference(reference)

        grid = gemmi.FloatGrid(*spacing)
        grid.unit_cell = unit_cell

        partitioning = Partitioning.from_reference(reference,
                                                   grid,
                                                   )

        return Grid(grid, partitioning)

    def new_grid(self):
        spacing = [self.grid.nu, self.grid.nv, self.grid.nw]
        unit_cell = self.grid.unit_cell
        grid = gemmi.FloatGrid(spacing[0], spacing[1], spacing[2])
        grid.unit_cell = unit_cell
        return grid

    @staticmethod
    def spacing_from_reference(reference: Reference):
        spacing = reference.reflections.reflections.get_size_for_hkl()
        return spacing

    @staticmethod
    def unit_cell_from_reference(reference: Reference):
        return reference.reflections.reflections.cell

    def __getitem__(self, item):
        return self.grid[item]


@dataclasses.dataclass()
class Transform:
    transform: gemmi.Transform

    def transform(self, positions: typing.Dict[typing.Tuple[int], gemmi.Position]):
        transformed_positions = {}
        for index, position in positions.items():
            transformed_positions[index] = self.transform.apply(position)

        return transformed_positions

    @staticmethod
    def from_translation_rotation(translation, rotation):
        transform = gemmi.Transform()
        transform.vec.fromlist(translation.tolist())
        transform.mat.fromlist(rotation.tolist())

        return Transform(transform)

    @staticmethod
    def from_residues(previous_res, current_res, next_res, previous_ref, current_ref, next_ref):
        previous_ca_pos = previous_res["ca"][0].pos
        current_ca_pos = current_res["ca"][0].pos
        next_ca_pos = next_res["ca"][0].pos

        previous_ref_ca_pos = previous_ref["ca"][0].pos
        current_ref_ca_pos = current_ref["ca"][0].pos
        next_ref_ca_pos = next_ref["ca"][0].pos

        matrix = [Transform.pos_to_list(previous_ca_pos),
                  Transform.pos_to_list(current_ca_pos),
                  Transform.pos_to_list(next_ca_pos), ]
        matrix_ref = [Transform.pos_to_list(previous_ref_ca_pos),
                      Transform.pos_to_list(current_ref_ca_pos),
                      Transform.pos_to_list(next_ref_ca_pos), ]

        mean = np.mean(matrix, axis=0)
        mean_ref = np.mean(matrix_ref, axis=0)

        vec = mean_ref - mean

        de_meaned = matrix - mean
        de_meaned_ref = matrix_ref - mean_ref

        rotation = scipy.spatial.transform.Rotation.align_vectors(de_meaned, de_meaned_ref).rotation

        return Transform.from_translation_rotation(vec, rotation)

    @staticmethod
    def pos_to_list(pos: gemmi.Position):
        return [pos[0], pos[1], pos[2]]

    @staticmethod
    def from_start_residues(current_res, next_res, current_ref, next_ref):
        current_ca_pos = current_res["ca"][0].pos
        next_ca_pos = next_res["ca"][0].pos

        current_ref_ca_pos = current_ref["ca"][0].pos
        next_ref_ca_pos = next_ref["ca"][0].pos

        matrix = [
            Transform.pos_to_list(current_ca_pos),
            Transform.pos_to_list(next_ca_pos), ]
        matrix_ref = [
            Transform.pos_to_list(current_ref_ca_pos),
            Transform.pos_to_list(next_ref_ca_pos), ]

        mean = np.mean(matrix, axis=0)
        mean_ref = np.mean(matrix_ref, axis=0)

        vec = mean_ref - mean

        de_meaned = matrix - mean
        de_meaned_ref = matrix_ref - mean_ref

        rotation = scipy.spatial.transform.Rotation.align_vectors(de_meaned, de_meaned_ref).rotation

        return Transform.from_translation_rotation(vec, rotation)

    @staticmethod
    def from_finish_residues(previous_res, current_res, previous_ref, current_ref):
        previous_ca_pos = previous_res["ca"][0].pos
        current_ca_pos = current_res["ca"][0].pos

        previous_ref_ca_pos = previous_ref["ca"][0].pos
        current_ref_ca_pos = current_ref["ca"][0].pos

        matrix = [Transform.pos_to_list(previous_ca_pos),
                  Transform.pos_to_list(current_ca_pos), ]
        matrix_ref = [Transform.pos_to_list(previous_ref_ca_pos),
                      Transform.pos_to_list(current_ref_ca_pos), ]

        mean = np.mean(matrix, axis=0)
        mean_ref = np.mean(matrix_ref, axis=0)

        vec = mean_ref - mean

        de_meaned = matrix - mean
        de_meaned_ref = matrix_ref - mean_ref

        rotation = scipy.spatial.transform.Rotation.align_vectors(de_meaned, de_meaned_ref).rotation

        return Transform.from_translation_rotation(vec, rotation)


@dataclasses.dataclass()
class Alignment:
    transforms: typing.Dict[ResidueID, Transform]

    def __getitem__(self, item: ResidueID):
        return self.transforms[item]

    @staticmethod
    def from_dataset(reference: Reference, dataset: Dataset):

        transforms = {}

        for model in dataset.structure.structure:
            for chain in model:
                for res in chain.get_polymer():
                    prev_res = chain.previous_residue(res)
                    next_res = chain.next_residue(res)

                    prev_res_id = ResidueID.from_residue_chain(model, chain, prev_res)
                    current_res_id = ResidueID.from_residue_chain(model, chain, prev_res)
                    next_res_id = ResidueID.from_residue_chain(model, chain, prev_res)

                    prev_res_ref = reference.structure[prev_res_id]
                    current_res_ref = reference.structure[current_res_id]
                    next_res_ref = reference.structure[next_res_id]

                    if not prev_res:
                        transform = Transform.from_start_residues(res, next_res,
                                                                  current_res_ref, next_res_ref)

                    if not next_res:
                        transform = Transform.from_finish_residues(prev_res, res,
                                                                   prev_res_ref, current_res_ref)

                    else:
                        transform = Transform.from_residues(prev_res, res, next_res,
                                                            prev_res_ref, current_res_ref, next_res_ref,
                                                            )

                    transforms[current_res_id] = transform

        return Alignment(transforms)

    def __iter__(self):
        for res_id in self.transforms:
            yield res_id


@dataclasses.dataclass()
class Alignments:
    alignments: typing.Dict[Dtag, Alignment]

    @staticmethod
    def from_datasets(reference: Reference, datasets: Datasets):
        alignments = {dtag: Alignment.from_dataset(reference, datasets[dtag])
                      for dtag
                      in datasets
                      }
        return Alignments(alignments)

    def __getitem__(self, item):
        return self.alignments[item]


@dataclasses.dataclass()
class Resolution:
    resolution: float

    @staticmethod
    def from_float(res: float):
        return Resolution(res)

    def to_float(self) -> float:
        return self.resolution


@dataclasses.dataclass()
class Shell:
    test_dtags: typing.List[Dtag]
    train_dtags: typing.List[Dtag]
    datasets: Datasets
    res_max: Resolution
    res_min: Resolution


@dataclasses.dataclass()
class Shells:
    shells: typing.Dict[int, Shell]

    @staticmethod
    def from_datasets(datasets: Datasets, resolution_binning: ResolutionBinning):

        sorted_dtags = list(sorted(datasets.datasets.keys(),
                                   key=lambda dtag: datasets[dtag].reflections.resolution().resolution,
                                   ))

        train_dtags = sorted_dtags[:resolution_binning.min_characterisation_datasets]

        shells = []
        shell_num = 0
        shell_dtags = []
        shell_res = datasets[sorted_dtags[0]].reflections.resolution().resolution
        for dtag in sorted_dtags:
            res = datasets[dtag].reflections.resolution().resolution

            if (len(shell_dtags) > resolution_binning.max_shell_datasets) or (
                    res - shell_res > resolution_binning.high_res_increment):
                shell = Shell(shell_dtags,
                              train_dtags,
                              Datasets({dtag: datasets[dtag] for dtag in datasets
                                        if dtag in shell_dtags or train_dtags}),
                              res_max=Resolution.from_float(shell_res),
                              res_min=Resolution.from_float(res),
                              )
                shells[shell_num] = shell

                shell_dtags = []
                shell_res = res
                shell_num = shell_num + 1

            shell_dtags.append(dtag)


@dataclasses.dataclass()
class Xmap:
    xmap: gemmi.FloatGrid

    @staticmethod
    def from_reflections(reflections: Reflections):
        pass

    @staticmethod
    def from_aligned_dataset(dataset: Dataset, alignment: Alignment, grid: Grid, structure_factors: StructureFactors):
        unaligned_xmap = dataset.reflections.reflections.transform_f_phi_to_map(structure_factors.f,
                                                                                structure_factors.phi,
                                                                                )

        interpolated_values_tuple = ([], [], [], [])

        for residue_id in alignment:
            alignment_positions: typing.Dict[typing.Tuple[int], gemmi.Position] = grid.partitioning[residue_id]

            transformed_positions: typing.Dict[typing.Tuple[int],
                                               gemmi.Position] = alignment[residue_id].transform(alignment_positions)

            interpolated_values: typing.Dict[typing.Tuple[int],
                                             float] = unaligned_xmap.interpolate(transformed_positions)

            interpolated_values_tuple = (interpolated_values[0] + [index[0] for index in interpolated_values],
                                         interpolated_values[1] + [index[1] for index in interpolated_values],
                                         interpolated_values[2] + [index[2] for index in interpolated_values],
                                         interpolated_values[3] + [interpolated_values[index] for index in
                                                                   interpolated_values],
                                         )

        new_grid = grid.new_grid()

        new_grid[interpolated_values_tuple[0:3]] = interpolated_values_tuple[3]

        return Xmap(new_grid)


@dataclasses.dataclass()
class Xmaps:
    Xmaps: typing.Dict[Dtag, Xmap]

    @staticmethod
    def from_datasets(datasets: Datasets):
        pass

    @staticmethod
    def from_aligned_datasets(datasets: Datasets, alignments: Alignments, grid: Grid,
                              structure_factors: StructureFactors):
        xmaps = {}
        for dtag in datasets:
            xmap = Xmap.from_aligned_dataset(datasets[dtag],
                                             alignments[dtag],
                                             grid,
                                             structure_factors)

            xmaps[dtag] = xmap

        return Xmaps(xmaps)


@dataclasses.dataclass()
class Model:
    @staticmethod
    def from_xmaps(xmaps: Xmaps):
        pass


@dataclasses.dataclass()
class Zmap:
    @staticmethod
    def from_xmap(model: Model, cmap: Xmap):
        pass


@dataclasses.dataclass()
class Zmaps:
    Zmaps: typing.Dict[Dtag, Zmap]

    @staticmethod
    def from_xmaps(model: Model, xmaps: Xmaps):
        pass


@dataclasses.dataclass()
class ReferenceMap:
    @staticmethod
    def from_reference(reference: Reference):
        pass


@dataclasses.dataclass()
class ClusterID:
    dtag: Dtag
    number: int


@dataclasses.dataclass()
class Cluster:
    @staticmethod
    def from_zmap(zmap: Zmap):
        pass


@dataclasses.dataclass()
class Clusters:
    clusters: typing.Dict[ClusterID, Cluster]

    @staticmethod
    def from_Zmaps(zmaps: Zmaps):
        pass

    def filter_size_and_peak(self):
        pass

    def filter_distance_from_protein(self):
        pass

    def group_close(self):
        pass

    def remove_symetry_pairs(self):
        pass


@dataclasses.dataclass()
class BDC:
    bdc: float

    @staticmethod
    def from_float(bdc: float):
        pass

    @staticmethod
    def From_cluster(xmap: Xmap, cluster: Cluster):
        pass


@dataclasses.dataclass()
class Euclidean3Coord:
    x: float
    y: float
    z: float


@dataclasses.dataclass()
class Site:
    Coordinates: Euclidean3Coord


@dataclasses.dataclass()
class Sites:
    sites: typing.Dict[int, Site]

    @staticmethod
    def from_clusters(clusters: Clusters):
        pass


@dataclasses.dataclass()
class Event:
    Site: Site
    Bdc: BDC
    Cluster: Cluster
    Coordinate: Euclidean3Coord


@dataclasses.dataclass()
class EventID:
    Dtag: Dtag
    Event_idx: EventIDX


@dataclasses.dataclass()
class Events:
    events: typing.Dict[EventID, Event]

    @staticmethod
    def from_clusters(clusters: Clusters):
        pass


@dataclasses.dataclass()
class ZMapFile:

    @staticmethod
    def from_zmap(zmap: Zmap):
        pass


@dataclasses.dataclass()
class ZMapFiles:

    @staticmethod
    def from_zmaps(zmaps: Zmaps):
        pass


@dataclasses.dataclass()
class EventMapFile:

    @staticmethod
    def from_event(event: Event, xmap: Xmap):
        pass


@dataclasses.dataclass()
class EventMapFiles:

    @staticmethod
    def from_events(events: Events, xmaps: Xmaps):
        pass


@dataclasses.dataclass()
class SiteTableFile:

    @staticmethod
    def from_events(events: Events):
        pass


@dataclasses.dataclass()
class EventTableFile:

    @staticmethod
    def from_events(events: Events):
        pass


@dataclasses.dataclass()
class Analyses:
    analyses_dir: Path
    pandda_analyse_events_file: Path

    @staticmethod
    def from_pandda_dir(pandda_dir: Path):
        analyses_dir = pandda_dir / PANDDA_ANALYSES_DIR
        pandda_analyse_events_file = pandda_dir / PANDDA_ANALYSE_EVENTS_FILE

        return Analyses(analyses_dir=analyses_dir,
                        pandda_analyse_events_file=pandda_analyse_events_file,
                        )


@dataclasses.dataclass()
class DatasetModels:
    path: Path

    @staticmethod
    def from_dir(path: Path):
        return DatasetModels(path=path)


@dataclasses.dataclass()
class LigandDir:
    pdbs: typing.List[Path]
    cifs: typing.List[Path]
    smiles: typing.List[Path]

    @staticmethod
    def from_path(path):
        pdbs = list(path.glob("*.pdb"))
        cifs = list(path.glob("*.cifs"))
        smiles = list(path.glob("*.smiles"))

        return LigandDir(pdbs,
                         cifs,
                         smiles,
                         )


@dataclasses.dataclass()
class DatasetDir:
    input_pdb_file: Path
    input_mtz_file: Path
    ligand_dir: LigandDir

    @staticmethod
    def from_path(path: Path, input_settings: Input):
        input_pdb_file: Path = next(path.glob(input_settings.pdb_regex))
        input_mtz_file: Path = next(path.glob(input_settings.mtz_regex))
        ligand_dir: LigandDir = LigandDir.from_path(path / PANDDA_LIGAND_FILES_DIR)

        return DatasetDir(input_pdb_file=input_pdb_file,
                          input_mtz_file=input_mtz_file,
                          ligand_dir=ligand_dir,
                          )


@dataclasses.dataclass()
class DataDirs:
    dataset_dirs: typing.Dict[Dtag, DatasetDir]

    @staticmethod
    def from_dir(directory: Path, input_settings: Input):
        dataset_dir_paths = list(directory.glob("*"))

        dataset_dirs = {}

        for dataset_dir_path in dataset_dir_paths:
            dtag = Dtag(dataset_dir_path.name)
            dataset_dir = DatasetDir.from_path(dataset_dir_path, input_settings)
            dataset_dirs[dtag] = dataset_dir

        return DataDirs(dataset_dirs)

    def to_dict(self):
        return self.dataset_dirs


@dataclasses.dataclass()
class ProcessedDataset:
    path: Path
    dataset_models: DatasetModels
    input_mtz: Path
    input_pdb: Path

    @staticmethod
    def from_dataset_dir(dataset_dir: DatasetDir, processed_dataset_dir: Path) -> ProcessedDataset:
        dataset_models_dir = processed_dataset_dir / PANDDA_MODELLED_STRUCTURES_DIR
        input_mtz = dataset_dir.input_mtz_file
        input_pdb = dataset_dir.input_pdb_file

        return ProcessedDataset(path=processed_dataset_dir,
                                dataset_models=DatasetModels.from_dir(dataset_models_dir),
                                input_mtz=input_mtz,
                                input_pdb=input_pdb,
                                )


@dataclasses.dataclass()
class ProcessedDatasets:
    processed_datasets: typing.Dict[Dtag, ProcessedDataset]

    @staticmethod
    def from_data_dirs(data_dirs: DataDirs, processed_datasets_dir: Path):
        processed_datasets = {}
        for dtag, dataset_dir in data_dirs.dataset_dirs.items():
            processed_datasets[dtag] = ProcessedDataset.from_dataset_dir(dataset_dir,
                                                                         processed_datasets_dir / dtag.dtag,
                                                                         )

        return ProcessedDatasets(processed_datasets)


@dataclasses.dataclass()
class PanDDAFSModel:
    pandda_dir: Path
    data_dirs: DataDirs
    analyses: Analyses
    processed_datasets: ProcessedDatasets

    @staticmethod
    def from_dir(input_data_dirs: Path,
                 output_out_dir: Path,
                 input_settings: Input,
                 ):
        analyses = Analyses.from_pandda_dir(output_out_dir)
        data_dirs = DataDirs.from_dir(input_data_dirs, input_settings)
        processed_datasets = ProcessedDatasets.from_data_dirs(data_dirs,
                                                              output_out_dir / PANDDA_PROCESSED_DATASETS_DIR,
                                                              )

        return PanDDAFSModel(pandda_dir=output_out_dir,
                             data_dirs=data_dirs,
                             analyses=analyses,
                             processed_datasets=processed_datasets,
                             )


@dataclasses.dataclass()
class RMSD:
    rmsd: float

    @staticmethod
    def from_structures(structure_1: Structure, structure_2: Structure):
        distances = []

        positions_1 = []
        positions_2 = []

        for residues_id in structure_1.residue_ids():
            res_1 = structure_1[residues_id][0]
            res_2 = structure_2[residues_id][0]

            res_1_ca = res_1["CA"][0]
            res_2_ca = res_2["CA"][0]

            res_1_ca_pos = res_1_ca.pos
            res_2_ca_pos = res_2_ca.pos
            print(res_1_ca_pos)
            print(res_2_ca_pos)

            positions_1.append(res_1_ca_pos)
            positions_2.append(res_2_ca_pos)

            distances.append(res_1_ca_pos.dist(res_2_ca_pos))

        positions_1_array = np.array([[x[0], x[1], x[2]] for x in positions_1])
        positions_2_array = np.array([[x[0], x[1], x[2]] for x in positions_2])

        return RMSD.from_arrays(positions_1_array, positions_2_array)
        #
        # distances_array = np.array(distances)
        # print(distances_array)
        # print((1.0 / distances_array.size) )
        # rmsd = np.sqrt((1.0 / distances_array.size) * np.sum(np.square(distances_array)))
        #
        # print(rmsd)
        #
        # return RMSD(rmsd)

    @staticmethod
    def from_arrays(array_1, array_2):
        array_1_mean = np.mean(array_1, axis=0)
        array_2_mean = np.mean(array_2, axis=0)

        print("#################################")
        print(array_1)
        print(array_1_mean)

        array_1_demeaned = array_1-array_1_mean
        array_2_demeaned = array_2-array_2_mean
        print(array_1_demeaned)

        print(array_1_demeaned-array_2_demeaned)

        rotation, rmsd = scipy.spatial.transform.Rotation.align_vectors(array_1_demeaned, array_2_demeaned)

        print(rotation)
        print(rmsd)

        return RMSD(rmsd)


    def to_float(self):
        return self.rmsd
