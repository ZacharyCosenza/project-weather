from typing import Dict
from kedro.pipeline import Pipeline
from weather_platform.pipelines import data_engineering, data_science


def register_pipelines() -> Dict[str, Pipeline]:
    de_pipeline = data_engineering.create_pipeline()
    ds_pipeline = data_science.create_pipeline()

    return {
        "data_engineering": de_pipeline,
        "data_science": ds_pipeline,
        "__default__": de_pipeline + ds_pipeline,
    }
