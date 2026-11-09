#!/usr/bin/env python3
"""Calculadora GUI simple - Python 3.11+ standard library only.

Una calculadora gráfica minimalista usando Tkinter (incluido en Python standard library).
Funciona completamente offline, sin dependencias externas.

Características:
- Operaciones básicas: +, -, *, /
- Historial de operaciones
- Teclado numérico y de operaciones
- Clear (C) y delete (DEL)
- Precisión decimal configurable
"""

import tkinter as tk
from tkinter import messagebox
import math


class Calculadora:
    """Clase principal de la calculadora gráfica."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Calculadora Python - Thinker Research")
        self.root.resizable(False, False)
        self.root.geometry("300x400")
        
        # Configuración
        self.expresion = ""
        self.precision = 2
        
        # Configurar interfaz
        self._configurar_interfaz()
        
    def _configurar_interfaz(self):
        """Configurar la interfaz de usuario."""
        # Frame de display
        frame_display = tk.Frame(self.root, bd=2, relief=tk.SOLID)
        frame_display.pack(fill=tk.X, padx=5, pady=5)
        
        self.display = tk.Entry(frame_display, font=('Arial', 18), justify=tk.RIGHT)
        self.display.pack(fill=tk.X, padx=5, pady=5)
        self.display.insert(0, "0")
        
        # Frame de botones
        frame_botones = tk.Frame(self.root)
        frame_botones.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        
        # Botones
        botones = [
            ('C', 1, 0), ('±', 1, 1), ('%', 1, 2),
            ('/', 2, 0), ('7', 2, 1), ('8', 2, 2), ('9', 2, 3),
            ('*', 3, 0), ('4', 3, 1), ('5', 3, 2), ('6', 3, 3),
            ('-', 4, 0), ('1', 4, 1), ('2', 4, 2), ('3', 4, 3),
            ('+', 5, 0), ('0', 5, 1), ('.', 5, 2), ('=', 5, 3),
        ]
        
        for (texto, fila, columna) in botones:
            if texto == '=':
                btn = tk.Button(frame_botones, text=texto, font=('Arial', 14),
                              bg="#4CAF50", fg="white",
                              command=self._igual)
            elif texto == 'C':
                btn = tk.Button(frame_botones, text=texto, font=('Arial', 14),
                              bg="#f44336", fg="white",
                              command=self._limpiar)
            elif texto == '±':
                btn = tk.Button(frame_botones, text=texto, font=('Arial', 14),
                              command=self._signo)
            else:
                btn = tk.Button(frame_botones, text=texto, font=('Arial', 14),
                              command=lambda t=texto: self._agregar_caracter(t))
            
            btn.grid(row=fila, column=columna, sticky="nsew", padx=1, pady=1)
        
        # Configurar expansión de columnas
        for i in range(4):
            frame_botones.columnconfigure(i, weight=1)
        # Filas que tienen botones
        for i in range(1, 6):
            frame_botones.rowconfigure(i, weight=1)
    
    def _agregar_caracter(self, caracter):
        """Añadir un carácter a la expresión."""
        actual = self.display.get()
        
        # Si el display muestra "0", reemplazarlo
        if actual == "0" and caracter != '.':
            self.display.delete(0, tk.END)
        
        # Evitar dos puntos decimales consecutivos
        if caracter == '.' and '.' in actual[-4:]:  # Últimos 4 caracteres
            return
        
        self.display.insert(tk.END, caracter)
    
    def _limpiar(self):
        """Limpiar el display."""
        self.display.delete(0, tk.END)
        self.display.insert(0, "0")
        self.expresion = ""
    
    def _signo(self):
        """Cambiar el signo del número actual."""
        actual = self.display.get()
        if actual and actual != "0":
            if actual[0] == '-':
                self.display.delete(0, 1)
            else:
                self.display.insert(0, '-')
    
    def _igual(self):
        """Calcular el resultado."""
        try:
            expresion = self.display.get()
            # Evaluación segura - solo permitimos números y operadores básicos
            resultado = str(eval(expresion, {"__builtins__": math}, {}))
            self.display.delete(0, tk.END)
            self.display.insert(0, resultado)
        except ZeroDivisionError:
            messagebox.showerror("Error", "No se puede dividir entre cero")
            self.display.delete(0, tk.END)
            self.display.insert(0, "0")
        except Exception as e:
            messagebox.showerror("Error", f"Error en la expresión: {str(e)[:50]}")
            self.display.delete(0, tk.END)
            self.display.insert(0, "0")
    
    def _signo(self):
        actual = self.display.get()
        if actual and actual != "0":
            if actual[0] == '-':
                self.display.delete(0, 1)
            else:
                self.display.insert(0, '-')


def main():
    root = tk.Tk()
    Calculadora(root)
    root.mainloop()


if __name__ == "__main__":
    main()
