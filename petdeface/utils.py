import subprocess
from pathlib import Path
import json
import sys


class InvalidBIDSDataset(Exception):
    def __init__(self, message, errors):
        super().__init__(message)
        self.errors = errors
        print(f"{message}\n{errors}")


def deno_validator_installed():
    get_help = subprocess.run(
        "bids-validator-deno --help", shell=True, capture_output=True
    )
    if get_help.returncode == 0:
        return True
    else:
        return False


def run_validator(bids_path):
    bids_path = Path(bids_path)
    if bids_path.exists():
        pass
    else:
        raise FileNotFoundError(bids_path)
    if deno_validator_installed():
        command = f"bids-validator-deno {bids_path.resolve()} --ignoreWarnings --json --no-color"
        run_validator = subprocess.run(command, shell=True, capture_output=True)
        json_output = json.loads(run_validator.stdout.decode("utf-8"))
        # since we've ignored warnings any issue in issue is an error
        issues = json_output.get("issues").get("issues")
        formatted_errors = ""
        for issue in issues:
            formatted_errors += "\n" + json.dumps(issue, indent=4)
        if formatted_errors != "":
            raise InvalidBIDSDataset(
                message=f"Dataset at {bids_path} is invalid, see:",
                errors=formatted_errors,
            )

    else:
        raise Exception(
            f"bids-validator-deno not found"
            + "\nskip validation with --skip_bids_validator"
            + "\nor install with pip install bids-validator-deno"
        )
