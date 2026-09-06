# re:Blue Android ARM64

Port experimental do [re:Blue](https://github.com/zolaware/reblue) para Android ARM64, com foco inicial na AYN Thor.

Este repositório é deliberadamente pequeno: em vez de copiar o código original, os workflows obtêm o `re:Blue` e o `ReXGlue SDK` oficiais e aplicam os patches Android deste projecto. Desta forma conseguimos acompanhar o upstream e manter separadas as alterações específicas de Android.

## Estado

**Actualização de 6 de setembro de 2026:** existem APKs locais até à v2.1,
mas este repositório ainda não contém todos os patches finais que os produziram.
O estado abaixo refere-se à preparação inicial do repositório.

A [auditoria do APK v2.1](docs/android-v21-audit.md) confirma os shaders HCG
sem Int64/BDA e identifica a perda da instrumentação nativa de arranque.
O novo `scripts/audit_android_apk.py` verifica o APK final, a assinatura,
o package, a ABI, os marcadores nativos e os shaders extraídos das bibliotecas.
Não foi feita uma nova build nem um teste na consola durante esta auditoria.

- [x] Repositório de trabalho criado
- [x] Estratégia Vulkan/SDL3/ANativeWindow definida
- [x] Patch inicial para re:Blue
- [x] Patch inicial para ReXGlue
- [ ] Validar patches contra o upstream actual
- [ ] Compilar ReXGlue para Android ARM64
- [ ] Separar o codegen host da runtime Android
- [ ] Gerar `libmain.so`
- [ ] Criar projecto Gradle/SDLActivity
- [ ] Gerar APK de smoke test
- [ ] Testar na AYN Thor

## Arquitectura do primeiro protótipo

O primeiro APK não terá o instalador dos três discos integrado. O objectivo é primeiro obter uma aplicação Android estável que arranque com uma instalação do jogo já preparada. Depois tratamos de armazenamento, instalação, actualizações e UX.

## Conteúdo protegido

Este repositório não contém ficheiros de Blue Dragon. A geração do código recompilado requer `default.xex` obtido da cópia legítima do utilizador e esse ficheiro não será publicado aqui.
