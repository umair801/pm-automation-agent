"""
Whisper transcription service.
Handles audio-to-text conversion for iOS voice memo captures.
This is the only module in the codebase that uses the OpenAI API.
"""

import structlog
from openai import AsyncOpenAI, APIStatusError, APIConnectionError
from app.utils.config import settings

logger = structlog.get_logger(__name__)

# Whisper model — only one option currently supported by the API.
WHISPER_MODEL = "whisper-1"

# Supported audio MIME types accepted by the iOS capture endpoint.
SUPPORTED_AUDIO_TYPES = {
    "audio/m4a",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/webm",
    "audio/ogg",
}


class WhisperServiceError(Exception):
    """Raised when a Whisper API transcription fails."""
    pass


class WhisperService:
    """
    Async wrapper around the OpenAI Whisper transcription API.
    Accepts raw audio bytes and returns a plain text transcript.
    """

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str,
        content_type: str = "audio/m4a",
        language: str = "en",
    ) -> str:
        """
        Transcribe an audio file using the Whisper API.

        Args:
            audio_bytes: Raw audio file content as bytes.
            filename: Original filename including extension (e.g. "memo.m4a").
                      Whisper uses the extension to detect the audio format.
            content_type: MIME type of the audio file.
            language: ISO 639-1 language code. Defaults to English.

        Returns:
            Transcribed text as a plain string.

        Raises:
            WhisperServiceError: If the content type is unsupported or the
                                 Whisper API call fails.
        """
        if content_type not in SUPPORTED_AUDIO_TYPES:
            raise WhisperServiceError(
                f"Unsupported audio type: {content_type}. "
                f"Supported types: {', '.join(sorted(SUPPORTED_AUDIO_TYPES))}"
            )

        logger.info(
            "whisper_transcription_start",
            filename=filename,
            content_type=content_type,
            audio_size_bytes=len(audio_bytes),
        )

        try:
            # The Whisper API expects a file-like tuple: (filename, bytes, content_type)
            response = await self._client.audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=(filename, audio_bytes, content_type),
                language=language,
                response_format="text",
            )

            # When response_format="text", the response is a plain string.
            transcript = response.strip() if isinstance(response, str) else str(response).strip()

            logger.info(
                "whisper_transcription_complete",
                transcript_length=len(transcript),
            )
            return transcript

        except APIConnectionError as e:
            logger.error("whisper_connection_error", error=str(e))
            raise WhisperServiceError(f"Whisper API connection failed: {e}") from e

        except APIStatusError as e:
            logger.error("whisper_status_error", status_code=e.status_code, error=str(e))
            raise WhisperServiceError(
                f"Whisper API error {e.status_code}: {e.message}"
            ) from e
