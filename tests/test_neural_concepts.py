"""Pruebas del subsistema neural opt-in con PyTorch (CPU, modelos diminutos)."""

import unittest

try:
    import torch
except ImportError:
    torch = None

if torch is not None:
    from neural_concepts import (QuantizedLinear, ResidualVectorQuantizer,
                                 TinyAutoregressiveModel, TinyMixtureOfExperts,
                                 distill_teacher_student, greedy_decode, prune_linear,
                                 quantize_linear, sequences_from_lists, sparsity,
                                 speculative_decode, train_lora)


@unittest.skipUnless(torch is not None, "Subsistema ML opt-in: torch no instalado")
class TestNeuralConcepts(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        torch.manual_seed(7)
        self.secuencias = sequences_from_lists([
            [1, 2, 3, 4], [2, 3, 4, 5], [3, 4, 5, 6], [4, 5, 6, 7],
        ])

    def test_destilacion_real_cambia_estudiante(self):
        profesor = TinyAutoregressiveModel()
        estudiante = TinyAutoregressiveModel()
        antes = estudiante.head.weight.detach().clone()
        history = distill_teacher_student(profesor, estudiante, self.secuencias, epochs=2)
        self.assertEqual(len(history), 2)
        self.assertTrue(all(v == v for v in history))
        self.assertFalse(torch.equal(antes, estudiante.head.weight))

    def test_lora_solo_cambia_adaptador(self):
        modelo = TinyAutoregressiveModel()
        pesos = modelo.head.weight.detach().clone()
        resultado = train_lora(modelo, self.secuencias, rank=2, epochs=2)
        self.assertEqual(len(resultado["history"]), 2)
        self.assertTrue(torch.equal(pesos, modelo.head.base.weight))
        self.assertGreater(float(resultado["adapter"]["b"].abs().sum()), 0)

    def test_cuantizacion_real_y_memoria(self):
        base = torch.nn.Linear(4, 3)
        entrada = torch.randn(2, 4)
        esperado = base(entrada)
        cuantizada = quantize_linear(base, bits=8)
        self.assertIsInstance(cuantizada, QuantizedLinear)
        self.assertEqual(cuantizada.weight_q.dtype, torch.int8)
        self.assertLess((cuantizada(entrada) - esperado).abs().max().item(), 0.05)
        self.assertGreater(cuantizada.memory_bytes()["savings_ratio"], 0.7)
        int4 = QuantizedLinear(base, bits=4)
        self.assertGreater(int4.memory_bytes()["savings_ratio"], 0.8)

    def test_poda_real_de_pesos(self):
        modelo = TinyAutoregressiveModel()
        for modulo in modelo.modules():
            if isinstance(modulo, torch.nn.Linear):
                prune_linear(modulo, amount=0.2)
        self.assertGreater(sparsity(modelo), 0.1)
        salida = modelo(self.secuencias)
        self.assertEqual(salida.shape, (4, 4, 32))

    def test_moe_selecciona_un_experto_por_token(self):
        moe = TinyMixtureOfExperts()
        entrada = torch.randn(2, 3, 8)
        salida, indices, probabilidades = moe(entrada)
        self.assertEqual(salida.shape, entrada.shape)
        self.assertEqual(indices.shape, (2, 3))
        self.assertTrue(torch.allclose(probabilidades.sum(dim=-1), torch.ones(2, 3)))
        salida.sum().backward()
        self.assertIsNotNone(moe.router.weight.grad)

    def test_speculative_equivale_greedy_con_menos_llamadas_target(self):
        target = TinyAutoregressiveModel()
        prefijo = [1, 2]
        pasos = 4
        esperado = greedy_decode(target, prefijo, pasos)
        resultado = speculative_decode(target, target, prefijo, pasos, draft_k=2)
        self.assertEqual(resultado["tokens"], esperado)
        self.assertLess(resultado["target_calls"], pasos)
        self.assertEqual(resultado["accepted_draft"], pasos)

    def test_residual_vq_reconstruye_por_niveles(self):
        vectores = torch.tensor([[0., 0.], [0.1, 0.], [5., 5.], [5.1, 5.]])
        vq = ResidualVectorQuantizer(2, codebook_sizes=(2, 2)).fit(vectores, iterations=3)
        niveles = vq.encode(vectores)
        reconstruido = vq.decode(niveles)
        self.assertEqual(reconstruido.shape, vectores.shape)
        self.assertEqual(len(niveles), 2)
        self.assertLess(vq.mse(vectores), float(vectores.pow(2).mean()))
        self.assertTrue(all(nivel.dtype == torch.long for nivel in niveles))


if __name__ == "__main__":
    unittest.main()
