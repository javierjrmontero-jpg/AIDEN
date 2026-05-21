import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";

interface Props {
  content: string;
}

export default function MarkdownRenderer({ content }: Props) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ className, children, ...props }: any) {
          const match = /language-(\w+)/.exec(className || "");
          const isInline = !match;
          return isInline ? (
            <code className="bg-gray-700 text-emerald-300 px-1.5 py-0.5 rounded text-xs font-mono" {...props}>
              {children}
            </code>
          ) : (
            <div className="my-3 rounded-xl overflow-hidden border border-gray-700">
              <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
                <span className="text-xs text-gray-400 font-mono">{match[1]}</span>
                <button
                  onClick={() => navigator.clipboard.writeText(String(children))}
                  className="text-xs text-gray-500 hover:text-emerald-400 transition-colors"
                >
                  Copiar
                </button>
              </div>
              <SyntaxHighlighter
                style={vscDarkPlus}
                language={match[1]}
                PreTag="div"
                customStyle={{ margin: 0, borderRadius: 0, background: "#1a1a2e", fontSize: "0.8rem" }}
                {...props}
              >
                {String(children).replace(/\n$/, "")}
              </SyntaxHighlighter>
            </div>
          );
        },
        h1: ({ children }) => <h1 className="text-xl font-bold text-gray-100 mt-4 mb-2">{children}</h1>,
        h2: ({ children }) => <h2 className="text-lg font-bold text-gray-100 mt-3 mb-2">{children}</h2>,
        h3: ({ children }) => <h3 className="text-base font-semibold text-gray-200 mt-2 mb-1">{children}</h3>,
        p: ({ children }) => <p className="text-gray-100 leading-relaxed mb-2">{children}</p>,
        ul: ({ children }) => <ul className="list-disc list-inside space-y-1 mb-2 text-gray-100">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 mb-2 text-gray-100">{children}</ol>,
        li: ({ children }) => <li className="text-gray-100 leading-relaxed">{children}</li>,
        blockquote: ({ children }) => (
          <blockquote className="border-l-4 border-emerald-500 pl-4 my-2 text-gray-400 italic">{children}</blockquote>
        ),
        table: ({ children }) => (
          <div className="overflow-x-auto my-3">
            <table className="w-full text-sm border-collapse">{children}</table>
          </div>
        ),
        thead: ({ children }) => <thead className="bg-gray-700">{children}</thead>,
        th: ({ children }) => (
          <th className="px-3 py-2 text-left text-gray-200 font-semibold border border-gray-600">{children}</th>
        ),
        td: ({ children }) => <td className="px-3 py-2 text-gray-300 border border-gray-700">{children}</td>,
        tr: ({ children }) => <tr className="even:bg-gray-800">{children}</tr>,
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:text-emerald-300 underline">
            {children}
          </a>
        ),
        strong: ({ children }) => <strong className="font-bold text-gray-100">{children}</strong>,
        em: ({ children }) => <em className="italic text-gray-300">{children}</em>,
        hr: () => <hr className="border-gray-700 my-4" />,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
