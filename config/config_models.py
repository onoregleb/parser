from typing import List

from pydantic import BaseModel, Field
import yaml


class Catalog(BaseModel):
    url: str = Field(..., description="URL of catalog")
    categories: List[str] = Field(..., description="List of category names")

    @property
    def urls(self):
        return [self.url.format(category=x) for x in self.categories]


class Config(BaseModel):
    page_loading_time: int = Field(..., description="Time to load page before parsing goods")
    male: Catalog = Field(..., description="Male catalog information")
    female: Catalog = Field(..., description="Female catalog information")

    @classmethod
    def from_yaml(cls, path_to_config: str) -> "Config":
        with open(path_to_config, "r") as file:
            data = yaml.safe_load(file)

        return Config.model_validate(data)
