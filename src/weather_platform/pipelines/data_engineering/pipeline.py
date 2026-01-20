from kedro.pipeline import Pipeline, node, pipeline
from .nodes import create_features


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline([
        node(
            func=create_features,
            inputs=["raw_weather_data", "params:data_engineering"],
            outputs="features",
            name="create_features_node",
        ),
    ])
