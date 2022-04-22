from universal_playlists.main import service_builder
from universal_playlists.services.services import *
import os
import pandas as pd
from tqdm import tqdm


class Evaluator:
    def __init__(self, dataset_path: Path):
        self.df = pd.read_csv(dataset_path)
        headers = self.df.columns.values
        header_servicetype_map = {
            "spotify": ServiceType.SPOTIFY,
            "ytm": ServiceType.YTM,
            "mb": ServiceType.MB,
        }

        service_types = [header_servicetype_map[header] for header in headers]
        self.services = {
            service_type.value: service_builder(
                service_type,
                service_type.value,
                config_path=Path("data/service_configs")
                / f"{service_type.name}_config.json",
            )
            for service_type in service_types
        }

    @staticmethod
    def get_prediction(
        source_service: StreamingService,
        target_service: StreamingService,
        uri: URI,
    ) -> Optional[URI]:
        track = source_service.pull_track(uri)
        matches = target_service.search_track(track)
        matches.sort(key=lambda x: track.similarity(x), reverse=True)
        matches = [match for match in matches if track.matches(match)]
        if len(matches) == 0:
            return None
        return matches[0].uris[0]

    def evaluate(
        self, source_service_type: ServiceType, target_service_type: ServiceType, n=10
    ):
        source_service = self.services[source_service_type.value]
        target_service = self.services[target_service_type.value]

        source_header = source_service_type.name.lower()
        target_header = target_service_type.name.lower()

        source_uris = [
            URI(service=source_service_type.value, uri=uri)
            for uri in self.df[source_header]
        ][:n]
        target_uris = [
            URI(service=target_service_type.value, uri=uri)
            for uri in self.df[target_header]
        ][:n]
        prediction_uris = [
            self.get_prediction(source_service, target_service, source_uri)
            for source_uri in tqdm(source_uris)
        ]

        correct = len(
            [
                target_uri
                for target_uri, prediction_uri in zip(target_uris, prediction_uris)
                if target_uri == prediction_uri
            ]
        )

        print(f"{correct}/{n} correct")
        num_none = len(
            [
                prediction_uri
                for prediction_uri in prediction_uris
                if prediction_uri is None
            ]
        )
        print(f"{num_none}/{n} predictions were None")

        # for p, t in zip(prediction_uris, target_uris):
        #     if p != t and p and t:
        #         print(
        #             f"https://musicbrainz.org/recording/{p.uri} -> https://musicbrainz.org/recording/{t.uri}"
        #         )


def main():
    os.chdir(Path(__file__).parent)

    evaluator = Evaluator(Path("data") / "dataset.csv")
    evaluator.evaluate(ServiceType.SPOTIFY, ServiceType.YTM, n=10)
