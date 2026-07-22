import Foundation
import Darwin

// Setup-only verifier. It has no signing, history mutation, activation, or order API.
let metadataRoot = "/Library/PrivilegedHelperTools/com.tios.intake-verifier.d"
let helperPath = metadataRoot + "/tios-intake-verifier"
let stateRoot = "/private/var/db/tios-intake"
let temporaryRoot = stateRoot + "/tmp"
let allowedSignersPath = stateRoot + "/trust/allowed_signers"
let revocationKRLPath = stateRoot + "/trust/revoked.krl"
let decisionNamespace = "tios-intake-decision-v1"
let trustNamespace = "tios-intake-trust-v1"
let evidenceNamespace = "tios-intake-evidence-v1"
let checkpointNamespace = "tios-intake-checkpoint-v1"
let receiptNamespace = "tios-intake-receipt-v1"
let maximumInputBytes = 1_048_576

enum VerificationFailure: Error, CustomStringConvertible {
    case message(String)
    var description: String {
        switch self { case .message(let value): return value }
    }
}

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}

func secureRegularFile(_ path: String, mode: mode_t, owner: uid_t = 0) throws {
    var info = stat()
    if lstat(path, &info) != 0 { throw VerificationFailure.message("missing required file") }
    if (info.st_mode & S_IFMT) != S_IFREG || info.st_uid != owner || info.st_gid != 0 || (info.st_mode & 0o7777) != mode || info.st_nlink != 1 {
        throw VerificationFailure.message("unsafe file ownership, mode, type, or link count")
    }
}

func secureDirectory(_ path: String, mode: mode_t) throws {
    var info = stat()
    if lstat(path, &info) != 0 { throw VerificationFailure.message("missing required directory") }
    if (info.st_mode & S_IFMT) != S_IFDIR || info.st_uid != 0 || info.st_gid != 0 || (info.st_mode & 0o7777) != mode {
        throw VerificationFailure.message("unsafe directory ownership, mode, or type")
    }
}

func checkInstalledState() throws {
    guard geteuid() == 0 else { throw VerificationFailure.message("helper is not running as root") }
    try secureRegularFile(helperPath, mode: 0o555)
    try secureDirectory(metadataRoot, mode: 0o555)
    try secureRegularFile(metadataRoot + "/MANIFEST.sha256", mode: 0o444)
    try secureRegularFile(metadataRoot + "/VERSION", mode: 0o444)
    try secureDirectory(stateRoot, mode: 0o700)
    try secureDirectory(stateRoot + "/trust", mode: 0o700)
    try secureDirectory(temporaryRoot, mode: 0o700)
    try secureDirectory(stateRoot + "/history", mode: 0o700)
    try secureDirectory(stateRoot + "/checkpoints", mode: 0o700)
    try secureRegularFile(allowedSignersPath, mode: 0o444)
    try secureRegularFile(revocationKRLPath, mode: 0o444)
}

func validateCanonicalValues(_ value: Any) throws {
    if let number = value as? NSNumber {
        if CFGetTypeID(number) != CFBooleanGetTypeID() {
            let kind = String(cString: number.objCType)
            if kind == "f" || kind == "d" { throw VerificationFailure.message("floating-point values are prohibited") }
        }
    } else if let text = value as? String {
        if text.unicodeScalars.contains(where: { $0.value < 32 || $0.value == 127 }) { throw VerificationFailure.message("control characters are prohibited") }
    } else if let array = value as? [Any] {
        for child in array { try validateCanonicalValues(child) }
    } else if let object = value as? [String: Any] {
        for (key, child) in object { try validateCanonicalValues(key); try validateCanonicalValues(child) }
    }
}

func readBoundedStandardInput() throws -> Data {
    var value = Data()
    while value.count <= maximumInputBytes {
        let remaining = maximumInputBytes + 1 - value.count
        let chunk = try FileHandle.standardInput.read(upToCount: min(65_536, remaining)) ?? Data()
        if chunk.isEmpty { break }
        value.append(chunk)
    }
    if value.isEmpty || value.count > maximumInputBytes { throw VerificationFailure.message("input is empty or too large") }
    return value
}

func canonicalJSON(_ value: Any) throws -> Data {
    guard JSONSerialization.isValidJSONObject(value) else { throw VerificationFailure.message("invalid JSON value") }
    return try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys, .withoutEscapingSlashes])
}

func strictObject(_ data: Data, keys: Set<String>) throws -> [String: Any] {
    let value = try JSONSerialization.jsonObject(with: data, options: [.fragmentsAllowed])
    guard let object = value as? [String: Any], Set(object.keys) == keys else { throw VerificationFailure.message("JSON fields mismatch") }
    try validateCanonicalValues(object)
    // Requiring the wire bytes to be canonical makes duplicate keys, floats, whitespace,
    // alternate escaping, and key substitution fail even though Foundation is the parser.
    if try canonicalJSON(object) != data { throw VerificationFailure.message("JSON is not canonical") }
    return object
}

func requireExactAllowedIdentity(_ reviewer: String) throws {
    let data = try Data(contentsOf: URL(fileURLWithPath: allowedSignersPath), options: [.mappedIfSafe])
    guard data.count <= maximumInputBytes, let text = String(data: data, encoding: .utf8) else { throw VerificationFailure.message("invalid allowed-signers file") }
    let matches = text.split(separator: "\n").filter { line in
        let trimmed = line.trimmingCharacters(in: .whitespaces)
        if trimmed.isEmpty || trimmed.hasPrefix("#") { return false }
        return trimmed.split(whereSeparator: { $0 == " " || $0 == "\t" }).first.map(String.init) == reviewer
    }
    if matches.count != 1 { throw VerificationFailure.message("reviewer identity is not an exact unique principal") }
}

func safeToken(_ value: Any, field: String) throws -> String {
    guard let text = value as? String, !text.isEmpty, text.count <= 128 else { throw VerificationFailure.message("invalid \(field)") }
    let allowed = CharacterSet(charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
    if text.unicodeScalars.contains(where: { !allowed.contains($0) }) { throw VerificationFailure.message("invalid \(field)") }
    return text
}

func makeSecureTemporaryFile(signature: Data) throws -> String {
    let template = temporaryRoot + "/signature.XXXXXXXX"
    var bytes = Array(template.utf8CString)
    let descriptor = mkstemp(&bytes)
    guard descriptor >= 0 else { throw VerificationFailure.message("cannot create confined temporary file") }
    let path = String(cString: bytes)
    if fchmod(descriptor, 0o600) != 0 || write(descriptor, [UInt8](signature), signature.count) != signature.count || fsync(descriptor) != 0 {
        close(descriptor); unlink(path); throw VerificationFailure.message("cannot write temporary signature")
    }
    close(descriptor)
    return path
}

func verifyDecision() throws {
    try checkInstalledState()
    let envelopeData = try readBoundedStandardInput()
    let envelope = try strictObject(envelopeData, keys: ["payload_base64", "reviewer_id", "signature_base64"])
    guard let payloadText = envelope["payload_base64"] as? String,
          let payload = Data(base64Encoded: payloadText),
          let signatureText = envelope["signature_base64"] as? String,
          let signature = Data(base64Encoded: signatureText), !signature.isEmpty else {
        throw VerificationFailure.message("invalid base64 input")
    }
    guard payload.count <= maximumInputBytes else { throw VerificationFailure.message("payload is too large") }
    let reviewer = try safeToken(envelope["reviewer_id"] as Any, field: "reviewer identity")
    try requireExactAllowedIdentity(reviewer)
    let signaturePath = try makeSecureTemporaryFile(signature: signature)
    defer { unlink(signaturePath) }
    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/usr/bin/ssh-keygen")
    process.arguments = ["-Y", "verify", "-f", allowedSignersPath, "-I", reviewer, "-n", decisionNamespace, "-s", signaturePath, "-r", revocationKRLPath]
    process.environment = ["PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"]
    let input = Pipe(); process.standardInput = input
    process.standardOutput = FileHandle.nullDevice; process.standardError = FileHandle.nullDevice
    try process.run(); input.fileHandleForWriting.write(payload); try input.fileHandleForWriting.close()
    process.waitUntilExit()
    guard process.terminationReason == .exit && process.terminationStatus == 0 else { throw VerificationFailure.message("signature verification failed") }
    let blockers = ["DECISION_SEMANTICS_UNVERIFIED", "EXTERNAL_ACTIVATION_INCOMPLETE", "TRUST_TIME_UNVERIFIED"]
    FileHandle.standardOutput.write(try canonicalJSON(["blockers":blockers, "execution_authority":"NONE", "reviewer_id":reviewer, "status":"SIGNATURE_VERIFIED_SEMANTICS_UNVERIFIED"]))
    FileHandle.standardOutput.write(Data("\n".utf8))
}

func status() throws {
    try checkInstalledState()
    let namespaces = [decisionNamespace, trustNamespace, evidenceNamespace, checkpointNamespace, receiptNamespace]
    FileHandle.standardOutput.write(try canonicalJSON(["execution_authority":"NONE", "initialized":true, "namespaces":namespaces, "status":"SETUP_ONLY_PENDING_EXTERNAL_ACTIVATION"]))
    FileHandle.standardOutput.write(Data("\n".utf8))
}

do {
    let arguments = Array(CommandLine.arguments.dropFirst())
    if arguments == ["status", "--json"] { try status() }
    else if arguments == ["verify-decision"] { try verifyDecision() }
    else { throw VerificationFailure.message("usage: tios-intake-verifier status --json | verify-decision") }
} catch { fail("verification refused: \(error)") }
