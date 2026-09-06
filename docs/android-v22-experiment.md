# APK v2.2 — experiência isolada no vertex shader HCG

APK: `reblue-android-arm64-v2.2-vs-capability-test.apk`

SHA256: `3e29cb2adac066637b2aed401b4ddecc6959e892472ca5f3cd8be993dbda17a8`

Package preservado: `org.reblue.android.saf`. Versão 22 / 2.2. API mínima 28.
Assinado com a chave persistente da v1.5. Instalar por cima sem desinstalar.

## Alteração efectuada

Experiência sobre o APK exacto da v2.1, não uma recompilação integral das fontes.
Retirada apenas a capability `RuntimeDescriptorArray` redundante do HCG VS.
O VS não contém `OpTypeRuntimeArray` nem recursos de descritores.
O PS, que efectivamente usa arrays, mantém-se byte a byte igual à v2.1.

Para preservar o tamanho do símbolo ELF, as duas palavras retiradas da
declaração foram substituídas por dois `OpNop` imediatamente antes de
`OpReturn`, dentro da função main. O assembly foi comparado: ignorando os dois
Nops e a capability retirada, é idêntico ao anterior. O resto do `libmain.so`
permanece exactamente igual, incluindo o código máquina ARM64.

As outras alterações limitam-se ao versionCode/versionName no manifesto e às
duas etiquetas de versão no DEX. Os checksums do DEX foram recalculados e a
ordenação da tabela de strings foi verificada. Não há alteração ao código
de importação nem ao caminho dos dados. A assinatura é regenerada no fim.

## Verificações efectuadas

- SHA256 da base v2.1 e do VS original verificados antes de editar.
- Assinatura da base e do APK final verificadas por `apksigner`.
- Certificado persistente: `49c6c9801b1528bd840180ee55d4c69ea453b3f71639cb714d30d786d3932c52`.
- Alinhamento ZIP verificado por `zipalign`.
- Package, versão, SDK mínimo e integridade do DEX confirmados no APK final.
- `spirv-dis` e `spirv-val --target-env vulkan1.1` nos shaders extraídos do APK final.
- VS final só declara `Shader`; VS/PS continuam sem Int64/BDA.
- PS final conserva SHA256 `1decce2c72de6b3daa2e71745a16bc49c56b771cb9a12aee8b00d96a77450a8b`.
- `librexruntime.so`, `libprobe.so` e `resources.arsc` iguais aos da v2.1.
- Não houve execução na consola.

## Limitação herdada, não corrigida

A instrumentação nativa `native-stage.log` / `N18` já estava ausente na v2.1
e continua ausente. O auditor geral continua a falhar precisamente nesses dois
checks; não foi alterado para os ocultar. Os diagnósticos Vulkan/PSO existentes
na v2.1 são preservados. Esta é uma build de experiência, não uma publicação
completa que satisfaça todos os critérios de diagnóstico de arranque.

## Teste do utilizador

Instalar por cima, iniciar o jogo e copiar o diagnóstico completo. O cabeçalho
deve identificar `re:Blue Android v2.2 diagnostic`. Verificar sobretudo:

```text
CreateHostGraphicsPipeline(pipeline) failed: VkResult=-13
[pso-fail-kind] ... hcg_blit=1
```

Se persistir, a retirada da capability redundante do VS não foi suficiente.
Se desaparecer, comparar com a v2.1 no mesmo dispositivo antes de atribuir
causalidade. O teste não altera BDA, vertex inputs, blending, culling, resolução
ou a cache de shaders do jogo. Não incorpora ainda as optimizações gerais
propostas para a Thor.

## Reprodução pelo agente

`scripts/build_v22_experiment.py` requer a base com o SHA256 exacto da v2.1,
a chave PK8 e certificado PEM persistentes, pyelftools e cryptography, e as
ferramentas `spirv-val`, `spirv-dis`, `zipalign` e `apksigner` no PATH.

```sh
python3 scripts/build_v22_experiment.py /caminho/base-v2.1.apk \
  --output /caminho/build-v22 \
  --key /caminho/privado/reblue-android-v15.pk8 \
  --cert /caminho/privado/reblue-android-v15-cert.pem
```

O `default.xex` foi entretanto localizado entre os ficheiros disponíveis do
utilizador. Isso permite retomar o codegen numa reconstrução posterior; não
foi usado, publicado ou incorporado neste APK de experiência.
