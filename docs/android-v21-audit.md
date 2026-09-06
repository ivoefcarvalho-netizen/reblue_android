# Auditoria do APK Android v2.1 — 6 de setembro de 2026

## Resultado

Auditoria estática do APK exacto fornecido anteriormente. Não houve execução
na AYN Thor e não foi criada uma versão nova do jogo.

O APK conserva o workaround dos shaders HCG, mas perdeu os marcadores da
instrumentação nativa de arranque presentes na v1.7. Não deve servir de base
para uma nova publicação sem recuperar essa instrumentação.

| Elemento | Evidência no APK v2.1 |
| --- | --- |
| Package | `org.reblue.android.saf` |
| Versão | `versionCode=21`, `versionName=2.1` |
| API mínima | 28 |
| ABI das três bibliotecas | ELF64 / AArch64 |
| SHA256 APK | `f2a70492105acc19bf13c1ecbef09bd3cf01de6ad479c50f488ae7a86a3ba24d` |
| SHA256 certificado declarado em v2/v3 | `49c6c9801b1528bd840180ee55d4c69ea453b3f71639cb714d30d786d3932c52` |
| HCG VS: tamanho / SHA256 | 1320 bytes / `5b89745deb51e88be59ecb525a316e3dd02fd2f34587df6675a373b72c67e030` |
| HCG PS: tamanho / SHA256 | 1436 bytes / `1decce2c72de6b3daa2e71745a16bc49c56b771cb9a12aee8b00d96a77450a8b` |
| `spirv-val --target-env vulkan1.1` | VS e PS aprovados |
| Int64 / PhysicalStorageBufferAddresses | Ausentes nos dois shaders |
| Modelo de memória | Logical / GLSL450 |
| Entradas VS declaradas | 0: float2, 7: float2, 10: float4 |
| Interface VS → PS | Cor: location 0 / float4; UV: location 1 / float2 |
| Push constants VS | float2 no offset 32, intervalo [32,40) |
| Push constants PS | uint nos offsets 24 e 28, intervalo [24,32) |
| Recursos PS | Texturas: set 0, binding 0; samplers: set 3, binding 0 |

A integridade da assinatura deste APK foi também confirmada com
`apksigner verify` dos Android Build Tools 35.0.0. A simples leitura do
certificado não seria suficiente. O auditor exige esta verificação separada;
se a ferramenta estiver ausente, a verificação de publicação falha explicitamente.

Ferramentas SPIR-V compiladas a partir de SPIRV-Tools
`907d104d2b7197b0207b7889671b149e1d1bc8ab`, com SPIRV-Headers
`f0bf307f7c49d26484db596185cece53c37701fc`.

## Regressão confirmada na instrumentação

Comparação directa das bibliotecas extraídas dos APKs guardados:

| Marcador no `libmain.so` | v1.7 | v2.1 |
| --- | --- | --- |
| `native-stage.log` | Presente | Ausente |
| `N18-after-app-OnInitialize-ok` | Presente | Ausente |

O `classes.dex` da v2.1 ainda contém `native-stage.log`. Procurar a string no
APK inteiro daria uma falsa garantia: é preciso verificar as bibliotecas
nativas separadamente. A ausência destes marcadores demonstra perda da
instrumentação original, não uma falha de Java, SDL ou do arranque do jogo.

Os marcadores `[pso-fail-kind]`, `[pso-fail-slot]`, `[pso-fail-elem]` e o erro
Vulkan detalhado continuam presentes no `libmain.so` da v2.1.

## Candidato adicional a teste, ainda sem conclusão causal

O VS declara `RuntimeDescriptorArray` e `SPV_EXT_descriptor_indexing`, mas não
contém `OpTypeRuntimeArray` nem recursos de descritores. O PS contém os arrays
e precisa dessa capacidade. Se a v2.1 continuar a falhar, uma experiência
controlada possível é retirar apenas a capacidade redundante do VS, mantendo
todo o restante código, estado da pipeline e shader PS. Não foi feito esse
teste na consola e não se conclui que esta declaração cause o erro -13.

## Verificação reutilizável

Instalar as dependências de `scripts/requirements-audit.txt` e disponibilizar
`spirv-dis`, `spirv-val` e `apksigner` no PATH. Depois do empacotamento e assinatura:

```sh
python3 scripts/audit_android_apk.py build/final.apk --output build/audit
```

O comando extrai os shaders por símbolos ELF do `libmain.so` dentro do APK,
valida-os, guarda os respectivos assemblies e produz `audit.json`. Falha com
código 1 se faltar qualquer condição exigida. Não altera nem assina o APK,
não precisa da chave privada e não acede ao dispositivo ou aos dados do jogo.
Para uma nova versão superior a 21, passar também `--minimum-version-code 22`.
Se os símbolos tiverem sido removidos, falha em vez de adivinhar os shaders.

A presença de strings não prova execução. Esta auditoria não confirma a
filtragem efectiva dos vertex inputs, a activação das features Vulkan, o
upload dos push constants, nem a correspondência dos layouts em runtime.
Também não confirma a correcção de InitLogging por procurar um caminho literal:
esse caminho pode ser construído em execução.

## Continuidade das fontes

O repositório auxiliar estava em `6e20502` e contém os transforms v12, mas
não as alterações finais locais da v2.1. O ambiente anterior de compilação,
as 219 unidades geradas e o projecto Android final não estavam neste checkout.
O APK e a chave persistente foram recuperados. Não se deve reconstruir um APK
a partir dos transforms v12 e apresentá-lo como sucessor fiel da v2.1.

Referências de código recuperadas (não equivalem a provar a proveniência do APK):

- re:Blue: `957ac623199ebb3cfe40f6af28bc4958490b6067`.
- Plume, submódulo desse commit: `de0f70f75087242ce92516dd587ecadff25385db`.
- XenosRecomp, submódulo desse commit: `339af41df2c23dbe3256c1c377716b81a0e0fe6b`.

Antes da próxima publicação, recuperar ou reconstruir de forma verificável os
patches finais, repor a instrumentação e usar a auditoria no APK assinado.
Preservar o package e a chave v1.5+, sem qualquer reinstalação que elimine dados.
