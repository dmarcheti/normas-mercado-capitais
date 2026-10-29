// Texto e OCR de PDF pelas bibliotecas nativas do macOS (PDFKit e Vision), sem dependência nova.
//
// Uso:
//   swift scripts/pdf_macos.swift texto <pdf>
//       texto de cada página pelo PDFKit (PDFPage.string), páginas separadas por form feed.
//   swift scripts/pdf_macos.swift ocr <pdf> [dpi]
//       renderiza cada página (300 dpi por padrão) e roda VNRecognizeTextRequest
//       (.accurate, pt-BR, correção de idioma), mais passadas extras para o que a .accurate
//       descarta (ver trechosExtras); linhas na ordem de leitura (y decrescente, depois x),
//       páginas separadas por form feed. Em stderr, uma linha por página: "CONF<TAB>página
//       <TAB>confiança média da .accurate<TAB>trechos da .accurate<TAB>trechos extras".
//   swift scripts/pdf_macos.swift pdf-teste <saida.pdf> <arquivo.txt>
//       gera um PDF simples (uma página por bloco separado por form feed) para os testes.
//
// scripts/pdf_macos.py compila este arquivo uma vez com swiftc (dados/bin/pdf_macos) e
// reutiliza o binário; compilar a cada chamada custa alguns segundos.

import CoreGraphics
import CoreText
import Foundation
import PDFKit
import Vision

func falhar(_ msg: String, _ codigo: Int32 = 1) -> Never {
    FileHandle.standardError.write((msg + "\n").data(using: .utf8)!)
    exit(codigo)
}

func abrir(_ caminho: String) -> PDFDocument {
    guard let doc = PDFDocument(url: URL(fileURLWithPath: caminho)) else {
        falhar("erro: não consegui abrir o PDF: \(caminho)", 2)
    }
    return doc
}

func texto(_ caminho: String) {
    let doc = abrir(caminho)
    var paginas: [String] = []
    for i in 0..<doc.pageCount {
        paginas.append(doc.page(at: i)?.string ?? "")
    }
    print(paginas.joined(separator: "\u{0C}"))
}

/// Página renderizada em escala de cinza com fundo branco, respeitando a rotação.
func renderizar(_ pagina: PDFPage, dpi: CGFloat) -> CGImage? {
    guard let ref = pagina.pageRef else { return nil }
    let caixa = pagina.bounds(for: .mediaBox)
    let girada = abs(pagina.rotation) % 180 == 90
    let escala = dpi / 72.0
    let w = Int(((girada ? caixa.height : caixa.width) * escala).rounded())
    let h = Int(((girada ? caixa.width : caixa.height) * escala).rounded())
    guard w > 0, h > 0,
          let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                              space: CGColorSpaceCreateDeviceGray(),
                              bitmapInfo: CGImageAlphaInfo.none.rawValue)
    else { return nil }
    ctx.setFillColor(gray: 1, alpha: 1)
    ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.interpolationQuality = .high
    ctx.scaleBy(x: escala, y: escala)
    let destino = CGRect(x: 0, y: 0, width: CGFloat(w) / escala, height: CGFloat(h) / escala)
    ctx.concatenate(ref.getDrawingTransform(.mediaBox, rect: destino, rotate: 0,
                                            preserveAspectRatio: true))
    ctx.drawPDFPage(ref)
    return ctx.makeImage()
}

struct Trecho {
    let texto: String
    let caixa: CGRect
    let confianca: Float
}

/// Junta os trechos em linhas: ordena por y decrescente; trechos cujo centro vertical cai a
/// menos de meia altura da linha corrente ficam na mesma linha, ordenados por x.
func linhas(_ trechos: [Trecho]) -> [String] {
    let ordenados = trechos.sorted {
        $0.caixa.midY != $1.caixa.midY ? $0.caixa.midY > $1.caixa.midY : $0.caixa.minX < $1.caixa.minX
    }
    var grupos: [[Trecho]] = []
    for t in ordenados {
        if let ultimo = grupos.last?.first,
           abs(ultimo.caixa.midY - t.caixa.midY) < 0.5 * min(ultimo.caixa.height, t.caixa.height) {
            grupos[grupos.count - 1].append(t)
        } else {
            grupos.append([t])
        }
    }
    return grupos.map { g in g.sorted { $0.caixa.minX < $1.caixa.minX }.map { $0.texto }.joined(separator: " ") }
}

func reconhecer(_ imagem: CGImage, regiao: CGRect? = nil, correcao: Bool = true,
                nivel: VNRequestTextRecognitionLevel = .accurate) throws -> [Trecho] {
    let pedido = VNRecognizeTextRequest()
    pedido.recognitionLevel = nivel
    pedido.recognitionLanguages = ["pt-BR"]
    pedido.usesLanguageCorrection = correcao
    if let r = regiao { pedido.regionOfInterest = r }
    try VNImageRequestHandler(cgImage: imagem, options: [:]).perform([pedido])
    let r = regiao ?? CGRect(x: 0, y: 0, width: 1, height: 1)
    return (pedido.results ?? []).compactMap { obs in
        guard let c = obs.topCandidates(1).first else { return nil }
        // caixa da região de interesse -> coordenadas normalizadas da página
        let b = obs.boundingBox
        let caixa = CGRect(x: r.minX + b.minX * r.width, y: r.minY + b.minY * r.height,
                           width: b.width * r.width, height: b.height * r.height)
        return Trecho(texto: c.string, caixa: caixa, confianca: c.confidence)
    }
}

/// Fração da área de `t` coberta por algum trecho de `outros`.
func cobertura(_ t: Trecho, _ outros: [Trecho]) -> CGFloat {
    let area = t.caixa.width * t.caixa.height
    guard area > 0 else { return 1 }
    return outros.map { o -> CGFloat in
        let i = o.caixa.intersection(t.caixa)
        return i.isNull ? 0 : i.width * i.height / area
    }.max() ?? 0
}

/// A passada .accurate descarta trechos curtos e isolados: o número do parágrafo no recuo
/// ("1.", "2.") e às vezes a última linha curta de um parágrafo ("Resolução CVM nº 175.").
/// Passadas extras recuperam o que falta; um trecho extra só entra se não estiver já coberto
/// (mais de 30% da área) por outro. Medido no Ofício-Circular SSE 4/2025: 24 de 35 números
/// de parágrafo só com a .accurate, 35 de 35 com as extras.
///   - faixa esquerda (12% da largura), .accurate, só o que tem cara de numeração;
///   - faixa esquerda (17%), .fast, só numeração (acha números que a anterior perde);
///   - página inteira, .fast, qualquer texto (linhas curtas descartadas pela .accurate).
let NUMERACAO = "^([0-9]{1,3}[.)º°-]?|[IVXLCivxlc]{1,6}[.)-]|[a-z][.)]|§ ?[0-9]{1,3}º?)$"
let EXTRAS: [(CGFloat, VNRequestTextRecognitionLevel, Bool)] = [
    (0.12, .accurate, true), (0.17, .fast, true), (1.0, .fast, false)]

func trechosExtras(_ imagem: CGImage, _ principais: [Trecho]) throws -> [Trecho] {
    var todos = principais, novos: [Trecho] = []
    for (largura, nivel, soNumeracao) in EXTRAS {
        let regiao = CGRect(x: 0, y: 0, width: largura, height: 1)
        for t in try reconhecer(imagem, regiao: regiao, correcao: !soNumeracao, nivel: nivel)
        where (!soNumeracao || t.texto.range(of: NUMERACAO, options: .regularExpression) != nil)
            && cobertura(t, todos) <= 0.3 {
            todos.append(t)
            novos.append(t)
        }
    }
    return novos
}

func ocr(_ caminho: String, dpi: CGFloat) {
    let doc = abrir(caminho)
    var paginas: [String] = []
    for i in 0..<doc.pageCount {
        guard let pagina = doc.page(at: i), let imagem = renderizar(pagina, dpi: dpi) else {
            FileHandle.standardError.write("CONF\t\(i + 1)\t0.0000\t0\t0\n".data(using: .utf8)!)
            paginas.append("")
            continue
        }
        var principais: [Trecho] = [], extras: [Trecho] = []
        do {
            principais = try reconhecer(imagem)
            extras = try trechosExtras(imagem, principais)
        } catch {
            falhar("erro: Vision falhou na página \(i + 1): \(error)", 3)
        }
        // confiança só da passada .accurate (a .fast dá valores grosseiros, 0,3/0,5/1)
        let media = principais.isEmpty ? 0
            : principais.map { Double($0.confianca) }.reduce(0, +) / Double(principais.count)
        FileHandle.standardError.write(String(format: "CONF\t%d\t%.4f\t%d\t%d\n", i + 1, media,
                                              principais.count, extras.count).data(using: .utf8)!)
        paginas.append(linhas(principais + extras).joined(separator: "\n"))
    }
    print(paginas.joined(separator: "\u{0C}"))
}

func pdfTeste(_ saida: String, _ entrada: String) {
    guard let conteudo = try? String(contentsOfFile: entrada, encoding: .utf8) else {
        falhar("erro: não consegui ler \(entrada)", 2)
    }
    var caixa = CGRect(x: 0, y: 0, width: 595, height: 842)  // A4 em pontos
    guard let ctx = CGContext(URL(fileURLWithPath: saida) as CFURL, mediaBox: &caixa, nil) else {
        falhar("erro: não consegui criar \(saida)", 2)
    }
    let fonte = CTFontCreateWithName("Helvetica" as CFString, 14, nil)
    for bloco in conteudo.components(separatedBy: "\u{0C}") {
        ctx.beginPDFPage(nil)
        let atrib = NSAttributedString(string: bloco, attributes: [
            NSAttributedString.Key(kCTFontAttributeName as String): fonte])
        let quadro = CTFramesetterCreateFrame(CTFramesetterCreateWithAttributedString(atrib),
                                              CFRange(location: 0, length: 0),
                                              CGPath(rect: caixa.insetBy(dx: 60, dy: 60), transform: nil), nil)
        CTFrameDraw(quadro, ctx)
        ctx.endPDFPage()
    }
    ctx.closePDF()
}

let args = CommandLine.arguments
let uso = "uso: pdf_macos texto <pdf> | ocr <pdf> [dpi] | pdf-teste <saida.pdf> <arquivo.txt>"
guard args.count >= 3 else { falhar(uso, 64) }
switch args[1] {
case "texto": texto(args[2])
case "ocr": ocr(args[2], dpi: args.count > 3 ? CGFloat(Double(args[3]) ?? 300) : 300)
case "pdf-teste":
    guard args.count >= 4 else { falhar(uso, 64) }
    pdfTeste(args[2], args[3])
default: falhar(uso, 64)
}
