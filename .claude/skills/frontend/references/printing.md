# Impressão / PDF — `PrintSheet` + primitivos `Doc*`

> Reference do gate `frontend`. Abra ANTES de construir qualquer documento imprimível (OS,
> orçamento, contrato, termo, procuração, check-list, relatório) ou rota pública por token com botão
> "Imprimir". Padrão fundido em **2026-10-01** a partir de dois apps que tinham cada um uma metade:
> a **infra** do promoservice (`PrintSheet`) e o **vocabulário de corpo** do kailos. **O kit fundido
> mora em `frontend/src/components/print/` — copie a pasta inteira.** Já vendorado em promoservice
> (3 arquivos), kailos e nexarena (+ `PrintableDocumentDialog.tsx` e `print-preview-context.ts`).
> O `DocumentSheet`/`.kdoc` antigo do kailos foi **removido** (migração concluída 2026-10-01).

**Princípio:** PDF no front = `window.print()` do navegador ("Salvar como PDF") sobre uma folha HTML.
Zero lib de PDF no cliente, um único mecanismo, uma única infra. O app só escolhe cabeçalho e corpo.

## Canônico (onde copiar)

| Peça                                                                        | Fonte                                                                                           |
| --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| **Kit fundido**: `PrintSheet` + `Doc*` + CSS embutido                       | kailos/promoservice `components/print/{PrintSheet.tsx, DocPrimitives.tsx, print-style.ts}`      |
| Prévia + "Imprimir / salvar PDF" (documento de loja/contrato)               | kailos `components/print/{PrintableDocumentDialog.tsx, print-preview-context.ts}`; uso em `components/documents/StorePrintDialog.tsx` + `StorePrintSheet.tsx` (cabeçalho da loja) |
| Templates de documento (molde de contrato/termo/orçamento/relatório)        | kailos `components/documents/templates/*` (`SaleContractDocument`, `DeliveryTermDocument`, `WarrantyTermDocument`…) + `document-blocks.tsx` (monta `DocFieldGrid` com dados do veículo) |
| Documento imprimível por tela (OS, orçamento, check-list)                   | promoservice `ServiceOrderPrintView`, `QuotePrintView`, `ChecklistPrintView`                    |
| Rota pública por token com botão imprimir                                   | promoservice `routes/orcamento/$token.tsx`, `components/portal/PortalPrintButton.tsx`           |

`PrintSheet` exporta `PRINT_ROOT_ID`/`PREVIEW_ROOT_ID` (`print-style.ts`) e `PrintPreviewContext`
(prévia inline vs portal). Documento novo usa sempre o kit de `components/print/`. Se um nome divergir deste
doc, **o código canônico vence** — atualize esta tabela.

## Anatomia

```tsx
<PrintSheet
  organizationName organizationCnpj organizationLogoUrl organizationLogoDisplay   // cabeçalho (OrgBrand)
  documentInfo={<>Nº 123 · 26/09/2026</>}      // bloco à direita do cabeçalho (omita se `title` já identifica)
  title="Contrato de compra e venda" subtitle="Placa ABC1D23" titleAlign="center"   // contratos/termos
  footer={<DocSignatures signers={[{ role: "Cliente", name, info: cpf }, { role: "Vendedor" }]} placeDate="UBERLÂNDIA-MG, 26 DE SETEMBRO DE 2026" />}
>
  <DocSection heading="Veículo" pagination="keep-together"><DocFieldGrid rows={[["Placa", plate], …]} /></DocSection>
  <DocSection heading="Itens"><DocTable columns={…} rows={…} footer={…} totals={[["Valor total", total]]} /></DocSection>
  <DocSection heading="Condições" pagination="new-page"><DocItem n="1.1">…</DocItem></DocSection>
</PrintSheet>
```

- **`PrintSheet`** (`PrintSheet.tsx`): `createPortal(<div id="print-sheet" className="hidden flex-col
  bg-white text-black">, document.body)`. Invisível na tela; no `@media print` vira `display:flex` e
  todo **irmão** direto do `body` vai a `display: none`. O CSS é **uma string** (`PRINT_STYLE` em
  `print-style.ts`, `PRINT_ROOT_ID = "print-sheet"`) injetada num `<style>` **dentro** do
  componente — não é arquivo `.css`, não vaza para o app e viaja junto na cópia entre projetos.
  Tudo escopado em `#print-sheet` com classes `doc-*` (nunca `.grid`/`.table`: a utility `.grid` do
  Tailwind já pôs `display:grid` numa `<table>`). Fora de `@layer`, então vence o preflight sem `!important`.
- **Regras de página** (no `PRINT_STYLE`): `@page { size: A4; margin: 14mm }` · `min-height: 269mm`
  (297 − 2×14) + `flex-col` → rodapé colado embaixo em documento curto sem travar a quebra em
  documento longo · `thead { display: table-header-group }` (cabeçalho da tabela repete a cada
  folha) · `tr`, `.print-keep-together`, `img` com `break-inside: avoid` · `.print-page-break
  { break-before: page }`.
- **Cabeçalho**: marca da org (`OrgBrand`, logo `h-12 w-32`) + CNPJ à esquerda, `documentInfo` à
  direita. `title`/`subtitle` (opcionais) sob o cabeçalho, `titleAlign="center"` para contrato/termo.
  **Rodapé de UMA linha** (`print-footer`, só o nome da org) — o rodapé nativo do navegador desenha na
  mesma faixa e não é suprimível por CSS; repetir logo+nome ali dobra a massa disputando espaço.
- **Assinaturas** = slot `footer` (`mt-auto pt-10`, `print-keep-together`) com **`DocSignatures`**:
  `signers: DocSigner[]` (`role` impresso sob a linha + `alt`, `name`, `info: string | string[]`,
  `signatureUrl` — a assinatura capturada no link público sai desenhada **sobre** a linha) e
  `placeDate` opcional. 1 assinante = centralizado; 2+ = duas colunas. (O antigo `SignatureBlock` do
  promoservice foi absorvido por `DocSignatures`.)
- **Primitivos** (`DocPrimitives.tsx`, sem conhecimento de domínio; só funcionam dentro do
  `PrintSheet`): `DocSection({ heading, pagination?: "keep-together" | "new-page", dataSlot? })` ·
  `DocItem({ n?, children })` (parágrafo numerado) · `DocFacts({ rows: [rótulo, valor][] })` ·
  `DocFieldGrid({ rows: DocField[], variant?: "boxed" | "plain" })` (quadro rótulo-pequeno/valor) ·
  `DocTable({ columns: DocColumn[] /* label, numeric?, nowrap? */, rows, footer?, totals?: [rótulo,
  valor][], empty?, variant?: "lines" | "grid" })` · `DocTotals({ rows, total })` · `DocPhotoGrid({
  photos: DocPhoto[] /* src, alt, caption? */ })` (3 colunas 4:3, foto nunca parte) ·
  `DocSignatures`. **Dados entram por props tipadas** — nunca JSX cru de tabela no template.
- **Tipografia do papel**: fonte **estática** (stack do sistema; o `print-style.ts` fixa a
  `font-family`). Fonte variável (Geist etc.) sai com glifo cortado no PDF do Chrome — o "letra
  comida" que só aparece no PDF. Papel é preto no branco: sem tema, sem identidade de app.
- **Identidade tipográfica própria (opt-in)**: `PrintSheet extraStyle={(rootId) => css}` injeta CSS
  escopado no id da raiz (`print-sheet` / `print-sheet-preview`) sem forkar o kit. Fonte própria
  só **TTF estático** servido pelo app (`/public/fonts/...`) com `@font-face` de família de nome
  próprio. Ex. canônico: kailos `components/documents/document-typography.ts` (contratos/termos
  em Source Serif 4 + Source Sans 3, ligado no `StorePrintSheet`).

## Prévia + imprimir (`PrintableDocumentDialog`)

A folha é renderizada **duas vezes**: prévia dentro do dialog (`PrintPreviewContext` = true → o `PrintSheet` sai inline, fundo
`bg-muted/40`) e a cópia do portal para o `window.print()` — esta só monta com `open && isReady`.
Botão **"Imprimir / salvar PDF"** desabilitado até o dado chegar; antes de imprimir
`await document.fonts.ready` (imprimir antes troca a letra no PDF). Texto do dialog explica "Salvar
como PDF". Dados do cabeçalho da loja vêm de endpoint próprio (`useDocumentHeader`), o resto a tela
já tem (`StorePrintDialog`).

## Rota pública por token (link do cliente)

`/orcamento/$token`, `/acompanhar/$token`, `/checklist/$token`, `/nota/$token`: rota **fora da casca**,
sem auth, que monta a **mesma** folha escondida + `PortalPrintButton` (`window.print()` + dica
"desmarque Cabeçalhos e rodapés"). A view de impressão consome um **subconjunto estrutural**
(`PrintableQuote`, promoservice) satisfeito pelo tipo interno e pelo público — o link do cliente é o espelho exato
da impressão, sem componente duplicado. Link expirado/inválido → `DeadDocumentCard`, nunca tela em
branco. Backend de token: gate `auth`/`integrations` conforme o caso.

## Adicionar um documento novo (checklist)

1. Template = componente que recebe `data` tipado e devolve `PrintSheet` +
   `Doc*` — nenhuma regra de `@media print` no template.
2. Tela: `PrintableDocumentDialog` (documento de loja/contrato) ou botão que monta o `PrintSheet`
   escondido na própria página (OS, check-list, público — `*PrintView` do promoservice).
3. Tabela longa → `DocTable` (thead repete, linha não quebra). Bloco que não pode ser cortado →
   `print-keep-together`. Quebra forçada → `print-page-break`.
4. Imagem: URL absoluta via `uploadsUrl()`/endpoint presigned (`<img>` relativo some no PDF).
5. Uma folha de cada vez no `body`: dois portais ao mesmo tempo escondem um ao outro (a regra
   `body > *:not(#id)` é global). Documento alternativo na mesma tela → monte só o ativo, ou ids
   distintos + `body:has(> #id)`.
6. Teste manual: Chrome → Ctrl+P → "Salvar como PDF", documento de 1 folha, de 2+ folhas (thead
   repetido, assinatura não órfã) e o link público.

## Anti-padrões

- **NUNCA** `body * { visibility: hidden }` + `position: absolute` (legado do nexarena
  `BudgetDocument`, em migração): `visibility` não tira o app do fluxo → páginas em branco e
  conteúdo cortado assim que o documento passa de 1 folha. É portal no `body` + irmãos `display:none`.
- **NUNCA** imprimir via `<iframe>`/`window.open` com HTML montado à mão, nem lib de PDF no cliente.
- **NUNCA** CSS de impressão em arquivo global do app (vaza para outras telas) nem em Tailwind
  inline no corpo do documento (prévia e papel divergem).
- **NUNCA** fonte variável ou fonte do tema do app na folha; **NUNCA** cor de tema/`dark:` no papel.
- **NUNCA** `<table>` cru no template — `DocTable`/`DocFacts`/`DocFieldGrid`.
- **NUNCA** duplicar o componente da folha para o link público — subconjunto estrutural compartilhado.
