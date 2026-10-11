from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

FEATURES = ["Type", "Air temperature [K]", "Process temperature [K]", "Rotational speed [rpm]", "Torque [Nm]", "Tool wear [min]"]
TARGET = "Machine failure"
EXCLUDED = ["UDI", "Product ID", "TWF", "HDF", "PWF", "OSF", "RNF", TARGET]

class SensorReading(BaseModel):
    model_config = ConfigDict(extra="forbid")
    machine_type: Literal["L", "M", "H"]
    air_temperature: float = Field(ge=0, le=1500)
    process_temperature: float = Field(ge=0, le=1500)
    rotational_speed: float = Field(ge=0, le=50000)
    torque: float = Field(ge=0, le=5000)
    tool_wear: float = Field(ge=0, le=100000)

    def to_features(self):
        return dict(zip(FEATURES, [self.machine_type, self.air_temperature, self.process_temperature,
                                  self.rotational_speed, self.torque, self.tool_wear]))
