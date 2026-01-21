# Tudunk beszélgetni?

**Igen, tudunk beszélgetni!** 🗣️

Ez a projekt egy intelligens ügynök, amely képes "beszélgetni" a kódról - vagyis válaszolni tud a forráskóddal kapcsolatos kérdéseidre.

## Hogyan működik a beszélgetés?

A projekt LangChain keretrendszerre épül, és egy interaktív ReAct ügynököt használ, amely:
- Megérti a természetes nyelvű kérdéseidet (magyarul vagy angolul)
- Elemzi a forráskódot különböző eszközökkel
- Strukturált válaszokat ad a kérdéseidre

## Példa használat

```bash
python main.py \
  --project-root "/path/to/your/project" \
  --prompt "Milyen fájlok használják az autentikációt?" \
  --debug
```

## További információ

- Lásd a [README.hu.md](README.hu.md) fájlt a részletes használati útmutatóért
- Lásd a [README.md](README.md) fájlt az angol nyelvű dokumentációért

---

**Megjegyzés:** Ez egy archivált/kísérleti projekt. Használd referenciaimplementációként, ne éles megoldásként.
