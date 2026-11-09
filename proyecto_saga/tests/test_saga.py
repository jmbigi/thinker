from orquestador import PasoSaga, OrquestadorSaga

def test_paso_saga_run_success():
    paso = PasoSaga("step1")
    result = paso.run()
    assert result["step"] == "step1"
    assert result["status"] == "success"

def test_paso_saga_idempotency():
    paso = PasoSaga("step1")
    token = "fixed-token"
    r1 = paso.run(token=token)
    r2 = paso.run(token=token)
    assert r1 is r2
    assert paso._cache[token] == r1

def test_paso_saga_compensar_no_func():
    paso = PasoSaga("step1")
    result = paso.compensar()
    assert result["compensated"] is False

def test_paso_saga_compensar_with_func():
    called = []
    def comp():
        called.append(True)
        return {"compensated": True}
    paso = PasoSaga("step1", compensacion=comp)
    result = paso.compensar()
    assert result["compensated"] is True
    assert called

def test_orquestador_agregar_paso():
    orq = OrquestadorSaga()
    paso = PasoSaga("step1")
    orq.agregar_paso(paso)
    assert len(orq.pasos) == 1
    assert orq.pasos[0] is paso

def test_orquestador_ejecutar_success():
    orq = OrquestadorSaga()
    orq.agregar_paso(PasoSaga("step1"))
    orq.agregar_paso(PasoSaga("step2"))
    result = orq.ejecutar()
    assert result["estado"] == "completed"
    assert len(result["historial"]) == 2
    assert result["id_saga"] is not None

def test_orquestador_ejecutar_failure_triggers_dlq_and_compensation():
    orq = OrquestadorSaga()
    fail_step = PasoSaga("fail_step")
    # Monkey patch run to always raise
    def always_fail(token=None):
        raise RuntimeError("boom")
    fail_step.run = always_fail
    
    comp_called = []
    def comp():
        comp_called.append(True)
        return {"compensated": True}
    prev_step = PasoSaga("prev_step", compensacion=comp)
    
    orq.agregar_paso(prev_step)
    orq.agregar_paso(fail_step)
    
    result = orq.ejecutar(max_retries=1, backoff_factor=0.01)
    
    assert result["estado"] == "failed"
    assert len(orq.dlq) == 0  # cleared after compensation
    assert comp_called  # compensation executed

def test_orquestador_retry_success():
    orq = OrquestadorSaga()
    attempts = []
    def flaky_run(token=None):
        attempts.append(1)
        if len(attempts) < 2:
            raise RuntimeError("transient")
        return {"step": "flaky", "status": "success", "result": "ok"}
    step = PasoSaga("flaky")
    step.run = flaky_run
    orq.agregar_paso(step)
    
    result = orq.ejecutar(max_retries=3, backoff_factor=0.01)
    
    assert result["estado"] == "completed"
    assert len(attempts) == 2

def test_orquestador_dlq_cleared_after_compensation():
    orq = OrquestadorSaga()
    step = PasoSaga("fail")
    step.run = lambda token: (_ for _ in ()).throw(RuntimeError("fail"))
    step.compensacion = lambda: {"compensated": True}
    orq.agregar_paso(step)
    
    orq.ejecutar(max_retries=1, backoff_factor=0.01)
    
    assert len(orq.dlq) == 0