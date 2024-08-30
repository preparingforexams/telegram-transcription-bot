import asyncio
import logging
from pathlib import Path

_LOG = logging.getLogger(__name__)


class AudioConverter:
    def __init__(self) -> None:
        pass

    async def convert_to_wave(self, input_file: Path) -> Path:
        output_file = input_file.with_suffix(".wav")
        if output_file == input_file:
            _LOG.info("Short-circuiting due to input file already having wave format")
            return input_file

        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-i",
            input_file,
            output_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()
        return_code = process.returncode
        if return_code:
            _LOG.error(
                "Converted file with exit code %d",
                return_code,
                extra=dict(stdout=stdout, stderr=stderr),
            )
            raise IOError("Could not convert file")

        return output_file
