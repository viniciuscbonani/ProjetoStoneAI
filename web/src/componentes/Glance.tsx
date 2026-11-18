import { ActionIcon, Tooltip } from "@mantine/core";
import { IconX } from "@tabler/icons-react";
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";

// Janela por cima da tela atual, como o Glance do Zen Browser: cresce a partir do que foi clicado, com o fundo
// escurecido, e volta para lá ao fechar. Os botões ficam do lado de fora, à direita (no celular, por dentro).
// Um glance pode abrir outro por cima (um Reel de dentro do banco de ganchos): Esc fecha só o de cima, e a página por
// baixo só volta a rolar quando não sobra nenhum.
const DURACAO = 320;
const pilha: number[] = [];
let proximoId = 0;
const CURVA = "cubic-bezier(0.2, 0.8, 0.2, 1)";
const semMovimento = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export default function Glance({ origem, onFechar, rotulo, largura = 1080, children }: {
  origem: DOMRect | null; onFechar: () => void; rotulo: string; largura?: number; children: ReactNode;
}) {
  const id = useRef(proximoId++).current;
  const painel = useRef<HTMLDivElement>(null);
  const fundo = useRef<HTMLDivElement>(null);
  const [fechando, setFechando] = useState(false);

  // Do centro do elemento clicado até o lugar final do painel (e o caminho de volta ao fechar).
  function quadros(): Keyframe[] {
    const p = painel.current!.getBoundingClientRect();
    if (!origem) return [{ transform: "translateY(24px) scale(0.96)", opacity: 0 }, { transform: "none", opacity: 1 }];
    const dx = origem.left + origem.width / 2 - (p.left + p.width / 2);
    const dy = origem.top + origem.height / 2 - (p.top + p.height / 2);
    const s = Math.max(0.08, Math.min(origem.width / p.width, 0.5));
    return [{ transform: `translate(${dx}px, ${dy}px) scale(${s})`, opacity: 0, borderRadius: "40px" }, { transform: "none", opacity: 1 }];
  }

  useLayoutEffect(() => {
    if (semMovimento()) return;
    painel.current?.animate(quadros(), { duration: DURACAO, easing: CURVA });
    fundo.current?.animate([{ opacity: 0 }, { opacity: 1 }], { duration: DURACAO, easing: "ease-out" });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function fechar() {
    if (fechando) return;
    if (semMovimento()) return onFechar();
    setFechando(true);
    painel.current?.animate([...quadros()].reverse(), { duration: DURACAO * 0.8, easing: CURVA, fill: "forwards" });
    fundo.current?.animate([{ opacity: 1 }, { opacity: 0 }], { duration: DURACAO * 0.8, fill: "forwards" });
    // Temporizador em vez de onfinish: com a aba em segundo plano, a animação fica parada e o onfinish não chega.
    setTimeout(onFechar, DURACAO * 0.8);
  }

  useEffect(() => {
    pilha.push(id);
    document.body.style.overflow = "hidden";
    return () => {
      pilha.splice(pilha.indexOf(id), 1);
      if (!pilha.length) document.body.style.overflow = "";
    };
  }, [id]);

  // Esc fecha só o glance de cima.
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Escape" && pilha[pilha.length - 1] === id) fechar();
    };
    document.addEventListener("keydown", tecla);
    return () => document.removeEventListener("keydown", tecla);
  }); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="glance" role="dialog" aria-modal="true" aria-label={rotulo}>
      <div ref={fundo} className="glance-fundo" onClick={fechar} />
      <div ref={painel} className="glance-painel" style={{ width: `min(${largura}px, calc(100vw - 140px))` }}>
        <div className="glance-botoes">
          <Tooltip label="Fechar (Esc)" position="right">
            <ActionIcon size={36} radius="xl" variant="default" onClick={fechar} aria-label="Fechar"><IconX size={18} /></ActionIcon>
          </Tooltip>
        </div>
        <div className="glance-conteudo">{children}</div>
      </div>
    </div>
  );
}
