import logging
import uuid
import time
from typing import Callable, Optional, Dict, Any

logger = logging.getLogger(__name__)

class PasoSaga:
    """Represents a single step in a saga."""
    def __init__(self, nombre: str, compensacion: Optional[Callable] = None):
        self.nombre = nombre
        self.compensacion = compensacion
        self._cache: Dict[str, Dict[str, Any]] = {}

    def run(self, token: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the step.
        If token is provided and already used, return cached result (idempotency).
        Otherwise perform the step and return result.
        """
        if token is None:
            token = str(uuid.uuid4())
        if token in self._cache:
            logger.debug("Idempotent call for step %s with token %s", self.nombre, token)
            return self._cache[token]

        # Simulate step execution (replace with real business logic)
        # For demonstration, we assume success unless we raise an error.
        result = {"step": self.nombre, "status": "success", "result": "completed"}
        self._cache[token] = result
        return result

    def compensar(self) -> Dict[str, Any]:
        """Execute compensation logic if defined."""
        if self.compensacion is None:
            return {"compensated": False}
        try:
            return self.compensacion()
        except Exception as e:
            logger.error("Compensation failed for step %s: %s", self.nombre, e)
            return {"compensated": False, "error": str(e)}

    def __repr__(self):
        return f"PasoSaga({self.nombre}, compensacion={self.compensacion})"


class OrquestadorSaga:
    """Orchestrator for a saga with steps, retries, DLQ, and idempotency."""
    def __init__(self):
        self.pasos = []  # list of PasoSaga
        self.dlq = []    # list of failed steps (each step object)
        self._pasos_completados = []  # steps successfully executed in the current run
        self._id_saga = None

    def agregar_paso(self, paso: PasoSaga) -> None:
        """Add a step to the saga."""
        self.pasos.append(paso)
        logger.info("Added step %s to saga", paso.nombre)

    def ejecutar(self, max_retries: int = 3, backoff_factor: float = 0.5) -> Dict[str, Any]:
        """
        Execute the saga.
        Returns a dict with keys:
            - id_saga: unique identifier for the saga
            - estado: "completed" or "failed"
            - historial: list of step results
            - idempotencia: token used (if any)
        """
        self._id_saga = str(uuid.uuid4())
        self._pasos_completados = []
        historial = []
        for paso in self.pasos:
            token = str(uuid.uuid4())
            try:
                result = paso.run(token=token)
                historial.append(result)
                self._pasos_completados.append(paso)
                # Step succeeded, continue to next step
            except Exception as e:
                logger.warning("Step %s failed on initial attempt: %s", paso.nombre, e)
                # Retry logic
                for attempt in range(1, max_retries + 1):
                    backoff = backoff_factor * (2 ** (attempt - 1))
                    logger.info("Retrying step %s (attempt %d) with backoff %.2f", paso.nombre, attempt, backoff)
                    try:
                        result = paso.run(token=token)
                        historial.append(result)
                        break  # success after retry
                    except Exception:
                        if attempt == max_retries:
                            logger.error("Step %s failed after %d retries", paso.nombre, max_retries)
                            # Add to DLQ
                            self.dlq.append(paso)
                            # Trigger compensation for previous steps
                            self._compensar_failed_steps()
                            # Mark saga as failed
                            return {
                                "id_saga": self._id_saga,
                                "estado": "failed",
                                "historial": historial,
                                "idempotencia": token
                            }
                        else:
                            # Continue to next attempt
                            time.sleep(backoff)
                else:
                    # Should not reach here
                    return {
                        "id_saga": self._id_saga,
                        "estado": "failed",
                        "historial": historial,
                        "idempotencia": token
                    }
        # All steps succeeded
        return {
            "id_saga": self._id_saga,
            "estado": "completed",
            "historial": historial,
            "idempotencia": token
        }

    def _compensar_failed_steps(self) -> None:
        """Compensate the steps already executed, in reverse order."""
        for paso in reversed(self._pasos_completados):
            resultado = paso.compensar()
            if resultado.get("compensated"):
                logger.info("Compensation succeeded for step %s", paso.nombre)
            else:
                logger.error("Compensation failed for step %s", paso.nombre)
        self._pasos_completados.clear()
        self.dlq.clear()

    def __repr__(self):
        return f"OrquestadorSaga(id_saga={self._id_saga}, pasos={len(self.pasos)}, dlq={len(self.dlq)})"