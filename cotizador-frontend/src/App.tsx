import React, { useMemo, useState } from "react";

const BACKEND = "http://127.0.0.1:8000"; // Cambia a IP del servidor si aplica
const LOGO_URL = `${BACKEND}/static/logo.png`;

type SimilarItem = {
  filename: string;
  similitud: number;
  url: string;
  precio_unitario_estimado?: number | null;
  descripcion_sugerida?: string | null;
};

type ResultadoBusqueda = { resultados: SimilarItem[] };

type CartItem = {
  filename: string;
  cantidad: number;
  descripcion: string;
  precio_unitario?: number;
  is_custom?: boolean;
  custom_filename?: string;
};

/* ===== Estilos base ===== */
const card: React.CSSProperties = {
  background: "#fff",
  border: "1px solid #e6e7eb",
  borderRadius: 16,
  padding: 16,
};

const input: React.CSSProperties = {
  width: "100%",
  height: 44,
  borderRadius: 12,
  border: "1px solid #e6e7eb",
  padding: "0 12px",
  background: "#fff",
};

const textArea: React.CSSProperties = {
  width: "100%",
  minHeight: 80,
  borderRadius: 12,
  border: "1px solid #e6e7eb",
  padding: 12,
  resize: "vertical",
  background: "#fff",
};

const btn: React.CSSProperties = {
  padding: "12px 18px",
  borderRadius: 12,
  border: "1px solid #0f172a",
  background: "#0f172a",
  color: "#fff",
  cursor: "pointer",
  fontWeight: 700,
};

const btnDanger: React.CSSProperties = {
  padding: "10px 14px",
  borderRadius: 10,
  border: "none",
  background: "#dc2626",
  color: "#fff",
  cursor: "pointer",
  fontWeight: 700,
};

/* ===== App ===== */
export default function App() {
  // Upload & preview
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  // Búsqueda
  const [resultados, setResultados] = useState<SimilarItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [perCardDesc, setPerCardDesc] = useState<Record<string, string>>({});

  // Carrito
  const [carrito, setCarrito] = useState<CartItem[]>([]);

  // Datos cliente (todos los campos)
  const [cliente, setCliente] = useState("");
  const [contacto, setContacto] = useState("");
  const [ruc, setRuc] = useState("");
  const [direccion, setDireccion] = useState("");
  const [fecha, setFecha] = useState("");
  const [tiempoProd, setTiempoProd] = useState("");
  const [condPago, setCondPago] = useState("");
  const [entrega, setEntrega] = useState("");
  const [observaciones, setObservaciones] = useState("");
  const [igvPct, setIgvPct] = useState(18);
  const [moneda, setMoneda] = useState("S/");
  const [cotizadoPor, setCotizadoPor] = useState("");

  // PDF
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);

  // “Ninguna coincide”
  const [miDesc, setMiDesc] = useState("");
  const [miCantidad, setMiCantidad] = useState("");
  const [miPU, setMiPU] = useState("");

  // Header
  const [logoError, setLogoError] = useState(false);

  const onFileChange = (f: File | null) => {
    setFile(f);
    setResultados([]);
    setPerCardDesc({});
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    if (f) setPreviewUrl(URL.createObjectURL(f));
    else setPreviewUrl(null);
  };

  const buscarSimilares = async () => {
    if (!file) return alert("Sube una imagen primero");
    setLoading(true);
    try {
      const form = new FormData();
      form.append("imagen", file);
      form.append("top_k", "8");
      const res = await fetch(`${BACKEND}/buscar-similares-imagen`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) throw new Error(await res.text());
      const data: ResultadoBusqueda = await res.json();
      setResultados(data.resultados || []);
      const d: Record<string, string> = {};
      (data.resultados || []).forEach((r) => (d[r.filename] = r.descripcion_sugerida || ""));
      setPerCardDesc(d);
    } catch (e) {
      console.error(e);
      alert("Error buscando similares");
    } finally {
      setLoading(false);
    }
  };

  const agregarAlCarrito = (r: SimilarItem) => {
    const cantidadStr = prompt("Cantidad:", "100");
    if (!cantidadStr) return;
    const cantidad = Number(cantidadStr);
    if (!cantidad || cantidad <= 0) return alert("Cantidad inválida");

    let pu: number | undefined = undefined;
    const basePU = r.precio_unitario_estimado ?? undefined;
    const puStr = prompt(
      `Precio unitario (Enter para usar ${basePU != null ? "S/ " + basePU.toFixed(2) : "—"})`,
      basePU != null ? String(basePU) : ""
    );
    if (puStr && puStr.trim() !== "") {
      const n = Number(puStr);
      if (!isFinite(n) || n < 0) return alert("P.U. inválido");
      pu = n;
    } else {
      pu = basePU;
    }

    const desc = (perCardDesc[r.filename] ?? r.descripcion_sugerida ?? "").trim();

    setCarrito((s) => [
      ...s,
      { filename: r.filename, cantidad, descripcion: desc, precio_unitario: pu },
    ]);
  };

  const usarMiImagenComoItem = async () => {
    if (!file) return alert("Primero sube una imagen");
    if (!miDesc.trim()) return alert("Ingresa una descripción");
    const c = Number(miCantidad);
    const pu = Number(miPU);
    if (!c || c <= 0) return alert("Cantidad inválida");
    if (!isFinite(pu) || pu < 0) return alert("P.U. inválido");

    try {
      const form = new FormData();
      form.append("imagen", file);
      const res = await fetch(`${BACKEND}/subir-imagen-custom`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as { filename: string; url: string };

      setCarrito((s) => [
        ...s,
        {
          filename: data.filename,
          custom_filename: data.filename,
          cantidad: c,
          descripcion: miDesc.trim(),
          precio_unitario: pu,
          is_custom: true,
        },
      ]);

      setMiDesc("");
      setMiCantidad("");
      setMiPU("");
      alert("Se agregó tu imagen como ítem al carrito");
    } catch (e) {
      console.error(e);
      alert("No se pudo usar tu imagen como ítem");
    }
  };

  const generarProforma = async () => {
    if (carrito.length === 0) return alert("Agrega al menos un item");
    if (!cliente.trim()) return alert("Ingresa el nombre del cliente");

    const payload = {
      datos: {
        cliente,
        contacto: contacto || undefined,
        ruc: ruc || undefined,
        direccion: direccion || undefined,
        fecha: fecha || undefined,
        tiempo_produccion: tiempoProd || undefined,
        condiciones_pago: condPago || undefined,
        entrega: entrega || undefined,
        observaciones: observaciones || undefined,
        igv_porcentaje: Number(igvPct),
        moneda,
        cotizado_por: cotizadoPor || undefined,
      },
      items: carrito.map((c) => ({
        filename: c.filename,
        cantidad: c.cantidad,
        descripcion: c.descripcion,
        precio_unitario_override:
          c.precio_unitario != null ? Number(c.precio_unitario) : undefined,
        is_custom: !!c.is_custom,
        custom_filename: c.is_custom ? c.custom_filename : undefined,
      })),
    };

    const res = await fetch(`${BACKEND}/generar-proforma`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      console.error(await res.text());
      alert("No se pudo generar la proforma");
      return;
    }
    const data = await res.json();
    setPdfUrl(`${BACKEND}${data.pdf_url}`);
    alert(`Proforma ${data.numero} generada`);
  };

  return (
    <div style={{ minHeight: "100vh", background: "#f6f7fb" }}>
      {/* Header centrado con logo pequeño */}
      <header
        style={{
          padding: "28px 16px",
          background: "#0f172a",
          color: "#e5e7eb",
          borderBottom: "1px solid #0b1223",
        }}
      >
        <div
          style={{
            maxWidth: 1200,
            margin: "0 auto",
            display: "grid",
            placeItems: "center",
            gap: 10,
            textAlign: "center",
          }}
        >
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: 16,
              background: "#ffffff",
              display: "grid",
              placeItems: "center",
              boxShadow: "0 4px 20px rgba(0,0,0,.25)",
              overflow: "hidden",
              padding: 8,
            }}
          >
            {!logoError ? (
              <img
                src={LOGO_URL}
                alt="Tinnova"
                style={{ width: "100%", height: "100%", objectFit: "contain" }}
                onError={() => setLogoError(true)}
              />
            ) : (
              <div
                style={{
                  width: "100%",
                  height: "100%",
                  display: "grid",
                  placeItems: "center",
                  color: "#111827",
                  fontWeight: 800,
                  fontSize: 22,
                }}
              >
                T
              </div>
            )}
          </div>
          <div style={{ fontWeight: 900, fontSize: 22, color: "#f8fafc" }}>
            Tinnova — Cotizador
          </div>
          <div style={{ color: "#cbd5e1", fontSize: 13 }}>
            Búsqueda visual + Proformas PDF
          </div>
        </div>
      </header>

      {/* Main */}
      <main
        style={{
          maxWidth: 1200,
          margin: "20px auto",
          padding: "0 16px",
          display: "grid",
          gridTemplateColumns: "minmax(520px, 560px) 1fr",
          gap: 16,
          alignItems: "start",
        }}
      >
        {/* Columna izquierda */}
        <div style={{ display: "grid", gap: 16 }}>
          {/* 1) Upload */}
          <section style={card}>
            <div style={{ fontWeight: 800, marginBottom: 8 }}>
              1) Buscar imágenes similares
            </div>
            <input
              type="file"
              accept="image/*"
              onChange={(e) => onFileChange(e.target.files?.[0] || null)}
            />
            {previewUrl && (
              <div
                style={{
                  marginTop: 12,
                  borderRadius: 12,
                  border: "1px solid #eef0f3",
                  padding: 8,
                  display: "flex",
                  gap: 12,
                  alignItems: "center",
                  background: "#fafafa",
                }}
              >
                <img
                  src={previewUrl}
                  alt="preview"
                  style={{
                    width: 84,
                    height: 84,
                    borderRadius: 12,
                    objectFit: "cover",
                  }}
                />
                <div style={{ fontSize: 12, color: "#374151" }}>
                  <div>
                    <b>Imagen subida</b>
                  </div>
                  <div>{file?.name}</div>
                </div>
              </div>
            )}
            <div style={{ height: 8 }} />
            <button style={btn} onClick={buscarSimilares} disabled={loading}>
              {loading ? "Buscando..." : "Buscar similares"}
            </button>
          </section>

          {/* 2) Datos del cliente (TODOS LOS CAMPOS, grilla responsiva) */}
          <section style={card}>
            <div style={{ fontWeight: 800, marginBottom: 8 }}>
              2) Datos del cliente
            </div>

            <div
              style={{
                display: "grid",
                gap: 10,
                gridTemplateColumns: "1fr",
              }}
            >
              <input
                style={input}
                placeholder="Cliente *"
                value={cliente}
                onChange={(e) => setCliente(e.target.value)}
              />

              {/* Dos columnas en pantallas anchas */}
              <div
                style={{
                  display: "grid",
                  gap: 10,
                  gridTemplateColumns: "1fr 1fr",
                }}
              >
                <input
                  style={input}
                  placeholder="Contacto"
                  value={contacto}
                  onChange={(e) => setContacto(e.target.value)}
                />
                <input
                  style={input}
                  placeholder="RUC"
                  value={ruc}
                  onChange={(e) => setRuc(e.target.value)}
                />
              </div>

              <input
                style={input}
                placeholder="Dirección"
                value={direccion}
                onChange={(e) => setDireccion(e.target.value)}
              />

              <div
                style={{
                  display: "grid",
                  gap: 10,
                  gridTemplateColumns: "1fr 1fr",
                }}
              >
                <input
                  style={input}
                  placeholder="Fecha (DD/MM/YYYY)"
                  value={fecha}
                  onChange={(e) => setFecha(e.target.value)}
                />
                <input
                  style={input}
                  placeholder="Tiempo de producción"
                  value={tiempoProd}
                  onChange={(e) => setTiempoProd(e.target.value)}
                />
              </div>

              <div
                style={{
                  display: "grid",
                  gap: 10,
                  gridTemplateColumns: "1fr 1fr",
                }}
              >
                <input
                  style={input}
                  placeholder="Condiciones de pago"
                  value={condPago}
                  onChange={(e) => setCondPago(e.target.value)}
                />
                <input
                  style={input}
                  placeholder="Entrega"
                  value={entrega}
                  onChange={(e) => setEntrega(e.target.value)}
                />
              </div>

              <textarea
                style={{ ...textArea, minHeight: 100 }}
                placeholder="Observaciones"
                value={observaciones}
                onChange={(e) => setObservaciones(e.target.value)}
              />

              <div
                style={{
                  display: "grid",
                  gap: 10,
                  gridTemplateColumns: "1fr 1fr 1fr",
                }}
              >
                <input
                  style={input}
                  type="number"
                  placeholder="IGV %"
                  value={igvPct}
                  onChange={(e) => setIgvPct(Number(e.target.value))}
                />
                <input
                  style={input}
                  placeholder="Moneda"
                  value={moneda}
                  onChange={(e) => setMoneda(e.target.value)}
                />
                <input
                  style={input}
                  placeholder="Cotizado por"
                  value={cotizadoPor}
                  onChange={(e) => setCotizadoPor(e.target.value)}
                />
              </div>
            </div>
          </section>

          {/* 3) Carrito amplio */}
          <section style={card}>
            <div style={{ fontWeight: 800, marginBottom: 8 }}>3) Carrito</div>
            {carrito.length === 0 && (
              <div style={{ color: "#6b7280" }}>No hay items agregados.</div>
            )}
            {carrito.map((c, idx) => (
              <div
                key={idx}
                style={{
                  border: "1px solid #eef0f3",
                  borderRadius: 12,
                  padding: 12,
                  marginBottom: 10,
                  background: "#fafafa",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 8,
                    alignItems: "center",
                  }}
                >
                  <div
                    style={{
                      fontWeight: 700,
                      fontSize: 12,
                      color: "#6b7280",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      maxWidth: "70%",
                    }}
                    title={c.filename}
                  >
                    {c.filename}
                  </div>
                  {c.is_custom && (
                    <span
                      style={{
                        padding: "2px 8px",
                        borderRadius: 999,
                        background: "#eef2ff",
                        color: "#3730a3",
                        fontSize: 11,
                        fontWeight: 700,
                      }}
                    >
                      Custom
                    </span>
                  )}
                </div>

                <div style={{ marginTop: 8 }}>
                  <label style={{ fontSize: 12, color: "#6b7280" }}>
                    Descripción (aparecerá en la proforma)
                  </label>
                  <textarea
                    style={{ ...textArea, minHeight: 160 }}
                    value={c.descripcion}
                    onChange={(e) =>
                      setCarrito((s) =>
                        s.map((x, i) =>
                          i === idx ? { ...x, descripcion: e.target.value } : x
                        )
                      )
                    }
                  />
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "160px 200px",
                    gap: 10,
                    marginTop: 8,
                  }}
                >
                  <div>
                    <label style={{ fontSize: 12, color: "#6b7280" }}>
                      Cantidad
                    </label>
                    <input
                      style={input}
                      type="number"
                      placeholder="Cantidad"
                      value={c.cantidad}
                      onChange={(e) =>
                        setCarrito((s) =>
                          s.map((x, i) =>
                            i === idx
                              ? { ...x, cantidad: Number(e.target.value) }
                              : x
                          )
                        )
                      }
                    />
                  </div>

                  <div>
                    <label style={{ fontSize: 12, color: "#6b7280" }}>
                      Precio unitario (override)
                    </label>
                    <input
                      style={input}
                      type="number"
                      step="0.01"
                      placeholder="P.U. (descuento)"
                      value={c.precio_unitario ?? ""}
                      onChange={(e) =>
                        setCarrito((s) =>
                          s.map((x, i) =>
                            i === idx
                              ? {
                                  ...x,
                                  precio_unitario:
                                    e.target.value === ""
                                      ? undefined
                                      : Number(e.target.value),
                                }
                              : x
                          )
                        )
                      }
                    />
                  </div>
                </div>

                <div style={{ marginTop: 10 }}>
                  <button style={btnDanger} onClick={() => setCarrito((s) => s.filter((_, i) => i !== idx))}>
                    Quitar
                  </button>
                </div>
              </div>
            ))}

            <div style={{ height: 8 }} />
            <button style={btn} onClick={generarProforma} disabled={carrito.length === 0}>
              Generar Proforma
            </button>
            {pdfUrl && (
              <div style={{ marginTop: 8 }}>
                <a href={pdfUrl} target="_blank" rel="noreferrer">
                  Descargar Proforma
                </a>
              </div>
            )}
          </section>
        </div>

        {/* Columna derecha: resultados + ninguna coincide */}
        <section style={{ ...card, minHeight: 400 }}>
          <div style={{ fontWeight: 800, marginBottom: 12 }}>Resultados</div>
          {resultados.length === 0 && (
            <div style={{ color: "#6b7280" }}>
              Sube una imagen y busca para ver coincidencias.
            </div>
          )}

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
              gap: 12,
            }}
          >
            {resultados.map((r) => (
              <div
                key={r.filename}
                style={{
                  border: "1px solid #eef0f3",
                  borderRadius: 14,
                  overflow: "hidden",
                  background: "#fff",
                }}
              >
                <div
                  style={{
                    height: 180,
                    display: "grid",
                    placeItems: "center",
                    background: "#fafafa",
                  }}
                >
                  <img
                    src={`${BACKEND}${r.url}`}
                    alt={r.filename}
                    style={{ maxWidth: "100%", maxHeight: 180, objectFit: "contain" }}
                  />
                </div>
                <div style={{ padding: 10 }}>
                  <div style={{ fontWeight: 700, fontSize: 12, color: "#6b7280" }}>
                    {r.filename}
                  </div>
                  <div style={{ fontSize: 12, color: "#374151", marginTop: 4 }}>
                    Sim: {r.similitud.toFixed(3)}
                  </div>
                  <div style={{ fontSize: 12, color: "#374151" }}>
                    P.U.:{" "}
                    {r.precio_unitario_estimado != null
                      ? `S/ ${r.precio_unitario_estimado.toFixed(2)}`
                      : "—"}
                  </div>

                  <div style={{ marginTop: 8, fontSize: 12, fontWeight: 600 }}>
                    Descripción sugerida
                  </div>
                  <textarea
                    value={perCardDesc[r.filename] ?? ""}
                    onChange={(e) =>
                      setPerCardDesc((s) => ({ ...s, [r.filename]: e.target.value }))
                    }
                    style={{ ...textArea, height: 110 }}
                  />

                  <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                    <button
                      style={btn}
                      onClick={() =>
                        agregarAlCarrito({
                          ...r,
                          descripcion_sugerida: perCardDesc[r.filename],
                        })
                      }
                    >
                      Agregar
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Bloque: Ninguna coincide */}
          <div style={{ marginTop: 16 }}>
            <section style={{ ...card, marginBottom: 0 }}>
              <div style={{ fontWeight: 800, marginBottom: 4 }}>
                ¿Ninguna coincide? Usa tu imagen
              </div>
              <div style={{ color: "#6b7280", fontSize: 12, marginBottom: 10 }}>
                Agrega este producto con tu descripción y precio unitario.
              </div>

              {/* Línea 1: Descripción ancha */}
              <div style={{ display: "grid", gap: 6, marginBottom: 10 }}>
                <label style={{ fontSize: 12, color: "#6b7280" }}>Descripción</label>
                <textarea
                  style={{ ...textArea, minHeight: 110 }}
                  placeholder="Descripción del producto"
                  value={miDesc}
                  onChange={(e) => setMiDesc(e.target.value)}
                />
              </div>

              {/* Línea 2: Cantidad + PU + Botón */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "200px 200px 1fr",
                  gap: 10,
                  alignItems: "end",
                }}
              >
                <div style={{ display: "grid", gap: 6 }}>
                  <label style={{ fontSize: 12, color: "#6b7280" }}>Cantidad</label>
                  <input
                    style={input}
                    type="text"
                    inputMode="numeric"
                    placeholder="Cantidad"
                    value={miCantidad}
                    onChange={(e) => setMiCantidad(e.target.value)}
                    aria-label="Cantidad"
                  />
                </div>

                <div style={{ display: "grid", gap: 6 }}>
                  <label style={{ fontSize: 12, color: "#6b7280" }}>
                    Precio unitario
                  </label>
                  <input
                    style={input}
                    type="text"
                    inputMode="decimal"
                    placeholder="Precio unitario"
                    value={miPU}
                    onChange={(e) => setMiPU(e.target.value)}
                    aria-label="Precio unitario"
                  />
                </div>

                <div style={{ display: "grid" }}>
                  <button style={btn} onClick={usarMiImagenComoItem}>
                    Agregar mi imagen
                  </button>
                </div>
              </div>
            </section>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer
        style={{
          padding: 20,
          textAlign: "center",
          color: "#6b7280",
        }}
      >
        © {new Date().getFullYear()} Tinnova S.A.C. — www.tinnova.promo
      </footer>
    </div>
  );
}
