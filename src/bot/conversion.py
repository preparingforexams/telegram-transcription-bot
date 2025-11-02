import asyncio
import logging
from typing import TYPE_CHECKING

from opentelemetry import trace

if TYPE_CHECKING:
    from pathlib import Path

_LOG = logging.getLogger(__name__)
_tracer = trace.get_tracer(__name__)


class AudioConverter:
    def __init__(self) -> None:
        pass

    async def convert_to_wave(self, input_file: Path) -> Path:
        with _tracer.start_as_current_span("convert_to_wave"):
            output_file = input_file.with_suffix(".wav")
            if output_file == input_file:
                _LOG.info(
                    "Short-circuiting due to input file already having wave format"
                )
                return input_file

            with _tracer.start_as_current_span("ffmpeg"):
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
                raise OSError("Could not convert file")

            return output_file
