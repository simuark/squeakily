# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/00_core.ipynb.

# %% auto 0
__all__ = ['logger', 'Pipeline']

# %% ../nbs/00_core.ipynb 2
import logging
import os

from datasets import concatenate_datasets, Dataset
from rich.logging import RichHandler

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(RichHandler(rich_tracebacks=True))
# Turn off logging for datasets
logging.getLogger("datasets").setLevel(logging.ERROR)

# %% ../nbs/00_core.ipynb 5
class Pipeline:
    """
    A pipeline is a collection of datasources and their associated transformations to be run.
    """

    def __init__(self, datasources):  # The datasources to be run
        self.datasources = datasources

    def __run_filter(self, dataset, column, filter_fn, dry_run, num_proc):
        """
        Run a filter on a dataset.
        """
        name = filter_fn.__name__
        logger.info(f"Running filter: {name} on {column}")
        if dry_run:
            logger.info(f"Running in dry-run mode")
            return dataset.map(
                lambda x: {f"{name}_criteria": filter_fn(x[column], dry_run=True)},
                num_proc=num_proc,
            )
        else:
            return dataset.filter(
                lambda x: filter_fn(x[column]),
                num_proc=num_proc,
            )

    def run(
        self,
        global_filters=[],  # Filters to be run at the dataset level rather than the example level
        global_cleaners=[],  # Cleaners to be run at the dataset level rather than the example level
        cleaning_first=False,  # Whether to run the cleaning transformations first
        globals_first=False,  # Whether to run the global transformations first
        dry_run=False,  # Whether to run the pipeline or only calculate the various criteria and add as a column
        num_proc=os.cpu_count(),  # Number of processes to use
    ):
        """
        Run the pipeline.
        """
        for i in range(len(self.datasources)):
            column = self.datasources[i]["columns"][0]
            logger.info(f"Running datasource: {self.datasources[i]['name']}")
            if cleaning_first:
                for c in self.datasources[i]["cleaners"]:
                    name = c.__name__
                    logger.info(f"Running cleaner: {name} on {column}")
                    self.datasources[i]["dataset"] = self.datasources[i]["dataset"].map(
                        lambda x: {column: c(x[column])},
                        num_proc=num_proc,
                    )
                for f in self.datasources[i]["filters"]:
                    self.datasources[i]["dataset"] = self.__run_filter(
                        self.datasources[i]["dataset"], column, f, dry_run, num_proc
                    )
            else:
                for f in self.datasources[i]["filters"]:
                    self.datasources[i]["dataset"] = self.__run_filter(
                        self.datasources[i]["dataset"], column, f, dry_run, num_proc
                    )
                for c in self.datasources[i]["cleaners"]:
                    name = c.__name__
                    logger.info(f"Running cleaner: {name} on {column}")
                    self.datasources[i]["dataset"] = self.datasources[i]["dataset"].map(
                        lambda x: {column: c(x[column])},
                        num_proc=num_proc,
                    )

        if len(global_filters) > 0:
            # concatenate all datasets
            datasets = [
                d["dataset"]
                for d in self.datasources
                if not d.get("skip_global", False)
            ]
            global_column = self.datasources[0]["columns"][0]
            global_dataset = concatenate_datasets(datasets)

            # Add a column representing the original dataset name
            md = []
            for d in self.datasources:
                if not d.get("skip_global", False):
                    md.extend([d["name"]] * len(d["dataset"]))
            meta_data = Dataset.from_dict({"meta_data": md})
            global_dataset_with_meta = concatenate_datasets(
                [global_dataset, meta_data], axis=1
            )

            # Run the global filters
            for f in global_filters:
                logger.info(f"Running global filter: {f.__name__}")
                global_dataset_with_meta = f(
                    global_dataset_with_meta, global_column, dry_run=dry_run
                )

            # Split the dataset back up
            for i, d in enumerate(self.datasources):
                if not d.get("skip_global", False):
                    self.datasources[i]["dataset"] = global_dataset_with_meta.filter(
                        lambda x: x["meta_data"] == d["name"],
                        num_proc=num_proc,
                    )
