import asyncio
import logging

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 15
MAX_OUTPUT_LENGTH = 5000

LANGUAGE_CONFIG = {
    "python": {
        "image": "python:3.12-slim",
        "cmd": ["python", "-c"],
    },
    "javascript": {
        "image": "node:22-slim",
        "cmd": ["node", "-e"],
    },
    "bash": {
        "image": "alpine:latest",
        "cmd": ["sh", "-c"],
    }
}

async def execute_code(code: str, language: str = "python") -> dict:
    config = LANGUAGE_CONFIG.get(language)
    if not config:
        return {
            "success": False,
            "output": "",
            "error": f"Lenguaje no soportado: {language}. Soportados: {list(LANGUAGE_CONFIG.keys())}",
            "exit_code": -1
        }

    try:
        cmd = [
            "docker", "run",
            "--rm",
            "--interactive",
            "--network", "none",
            "--memory", "128m",
            "--cpus", "0.5",
            config["image"],
            *config["cmd"], code
        ]

        logger.info(f"Ejecutando {language} en sandbox...")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            proc.kill()
            return {
                "success": False,
                "output": "",
                "error": f"Timeout: el código tardó más de {TIMEOUT_SECONDS} segundos",
                "exit_code": -1
            }

        output = stdout.decode("utf-8", errors="replace")
        error = stderr.decode("utf-8", errors="replace")

        if len(output) > MAX_OUTPUT_LENGTH:
            output = output[:MAX_OUTPUT_LENGTH] + "\n... (output truncado)"

        return {
            "success": proc.returncode == 0,
            "output": output,
            "error": error if proc.returncode != 0 else "",
            "exit_code": proc.returncode
        }

    except Exception as e:
        logger.error(f"Error en sandbox: {e}")
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "exit_code": -1
        }

# Mantener compatibilidad con el código existente
async def execute_python(code: str) -> dict:
    return await execute_code(code, "python")