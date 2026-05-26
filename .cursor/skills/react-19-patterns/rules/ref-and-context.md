# Ref-as-prop, Context-as-Provider, Document Metadata

Três simplificações que React 19 trouxe e que devem ser o default em código novo.

## 1. `ref` como prop direto — `forwardRef` é LEGADO

### Antes (React 18)

```tsx
import { forwardRef } from "react";

const Input = forwardRef<HTMLInputElement, InputProps>((props, ref) => {
  return <input ref={ref} {...props} />;
});
Input.displayName = "Input";
```

### Agora (React 19)

```tsx
interface InputProps extends React.ComponentProps<"input"> {
  ref?: React.Ref<HTMLInputElement>;
}

export function Input({ ref, ...props }: InputProps) {
  return <input ref={ref} {...props} />;
}
```

Mais simples, sem `displayName`, sem generics tortuosos. Funciona com `useRef`, callback ref, `useImperativeHandle`.

### Regra

- **Código novo:** ref como prop. NUNCA `forwardRef`.
- **Código existente com `forwardRef`:** deixar como está. Só migrar se já for tocar o arquivo. Não fazer refactoring em massa.
- Bibliotecas externas (shadcn antigo, radix) podem ainda usar `forwardRef` internamente — não tem problema, você consome igual.

## 2. Context como Provider direto — `<Context.Provider>` é LEGADO

### Antes

```tsx
const ThemeContext = createContext<Theme>(defaultTheme);

<ThemeContext.Provider value={theme}>
  <App />
</ThemeContext.Provider>;
```

### Agora

```tsx
const ThemeContext = createContext<Theme>(defaultTheme);

<ThemeContext value={theme}>
  <App />
</ThemeContext>;
```

### Regra

- Continua valendo a obrigatoriedade de **memoizar o `value`** com `useMemo` e deps primitivas. Inline `<Ctx value={{...}}>` em route component = cascade re-render. Ver `frontend.md > Performance`.
- `useContext(Ctx)` continua funcionando igual. (`use(Ctx)` também funciona — pode ser chamado condicionalmente.)

## 3. Document Metadata Inline

### Antes (com `react-helmet` ou similar)

```tsx
import { Helmet } from "react-helmet-async";

<Helmet>
  <title>Veículos — Kailos</title>
  <meta name="description" content="..." />
</Helmet>;
```

### Agora

```tsx
function VehiclesPage() {
  return (
    <>
      <title>Veículos — Kailos</title>
      <meta name="description" content="..." />
      <link rel="canonical" href="https://kailos.app/veiculos" />
      {/* resto da page */}
    </>
  );
}
```

React 19 detecta `<title>`, `<meta>`, `<link>` no JSX e move pro `<head>` automaticamente (hoisted).

### Regra

- **NUNCA** usar `react-helmet` / `react-helmet-async` em código novo.
- Em TanStack Router, isso convive bem com `<HeadContent />` quando você usa `head` na route — escolha um padrão por projeto (preferência: `head` da route + metadata inline para SPAs sem SSR).
- Para metadata dinâmica (Open Graph com dados da API), colocar dentro do componente que faz `use()` / `useQuery`, **após** os dados resolverem.

## Quando NÃO migrar

- Componente legado com `forwardRef` + `useImperativeHandle` em código existente, funcionando — surgical edits only, deixar como está.
- Lib de terceiros (shadcn @ radix antigo) — não tente "modernizar" o que veio do registry.
- Routing config com `head` já estabelecido — não duplicar via inline `<title>`.
