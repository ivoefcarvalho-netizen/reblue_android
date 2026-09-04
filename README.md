# re:Blue Android ARM64

Port experimental do [re:Blue](https://github.com/zolaware/reblue) para Android ARM64, com foco inicial na AYN Thor.

Este repositório é deliberadamente pequeno: em vez de copiar o código original, os workflows obtêm o `re:Blue` e o `ReXGlue SDK` oficiais e aplicam os patches Android deste projecto. Desta forma conseguimos acompanhar o upstream e manter separadas as alterações específicas de Android.

## Estado

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
