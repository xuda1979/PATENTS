import AppKit
import Foundation
import PDFKit

guard CommandLine.arguments.count == 3 else {
    fputs("usage: render_pdf INPUT.pdf OUTPUT_DIR\n", stderr)
    exit(2)
}

let input = URL(fileURLWithPath: CommandLine.arguments[1])
let output = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)

guard let document = PDFDocument(url: input) else {
    fputs("could not open PDF\n", stderr)
    exit(1)
}

for index in 0..<document.pageCount {
    guard let page = document.page(at: index) else { continue }
    let bounds = page.bounds(for: .mediaBox)
    let target = NSSize(width: bounds.width * 2.0, height: bounds.height * 2.0)
    let image = page.thumbnail(of: target, for: .mediaBox)
    guard
        let tiff = image.tiffRepresentation,
        let bitmap = NSBitmapImageRep(data: tiff),
        let png = bitmap.representation(using: .png, properties: [:])
    else {
        fputs("could not render page \(index + 1)\n", stderr)
        exit(1)
    }
    let filename = String(format: "page-%02d.png", index + 1)
    try png.write(to: output.appendingPathComponent(filename))
}

print("rendered \(document.pageCount) pages")
