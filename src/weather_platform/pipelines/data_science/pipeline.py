from kedro.pipeline import Pipeline, node, pipeline
from .nodes import prepare_model_data, train_model, evaluate_model


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline([
        node(
            func=prepare_model_data,
            inputs=["features", "params:data_science"],
            outputs=["train_data", "val_data", "test_data"],
            name="prepare_model_data_node",
        ),
        node(
            func=train_model,
            inputs=["train_data", "val_data", "params:data_science"],
            outputs="trained_model",
            name="train_model_node",
        ),
        node(
            func=evaluate_model,
            inputs=["trained_model", "test_data", "params:data_science"],
            outputs="model_metrics",
            name="evaluate_model_node",
        ),
    ])
