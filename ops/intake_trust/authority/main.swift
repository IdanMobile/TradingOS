import Foundation

// Source-only validator. It has no activation, admission, signing, or state-write API.
let maximumInputBytes = 1_048_576

enum Refusal: Error, CustomStringConvertible {
    case message(String)
    var description: String { switch self { case .message(let text): return text } }
}

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}

func readBoundedInput() throws -> Data {
    var data = Data()
    while data.count <= maximumInputBytes {
        let remaining = maximumInputBytes + 1 - data.count
        let chunk = try FileHandle.standardInput.read(upToCount: min(65_536, remaining)) ?? Data()
        if chunk.isEmpty { break }
        data.append(chunk)
    }
    if data.isEmpty || data.count > maximumInputBytes { throw Refusal.message("input is empty or too large") }
    return data
}

func validateValues(_ value: Any) throws {
    if let number = value as? NSNumber {
        if CFGetTypeID(number) != CFBooleanGetTypeID() {
            let type = String(cString: number.objCType)
            if type == "f" || type == "d" { throw Refusal.message("floating-point values are prohibited") }
        }
    } else if let text = value as? String {
        if text.unicodeScalars.contains(where: { $0.value < 32 || $0.value == 127 }) {
            throw Refusal.message("control characters are prohibited")
        }
    } else if let values = value as? [Any] {
        for child in values { try validateValues(child) }
    } else if let object = value as? [String: Any] {
        for (key, child) in object { try validateValues(key); try validateValues(child) }
    }
}

func canonicalJSON(_ value: Any) throws -> Data {
    guard JSONSerialization.isValidJSONObject(value) else { throw Refusal.message("invalid JSON value") }
    return try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys, .withoutEscapingSlashes])
}

func strictObject(_ data: Data, keys: Set<String>, domain: String) throws -> [String: Any] {
    let value = try JSONSerialization.jsonObject(with: data, options: [.fragmentsAllowed])
    guard let object = value as? [String: Any], Set(object.keys) == keys else { throw Refusal.message("JSON fields mismatch") }
    try validateValues(object)
    if try canonicalJSON(object) != data { throw Refusal.message("JSON is not canonical") }
    guard object["schema_version"] as? Int == 1,
          object["domain_separator"] as? String == domain,
          object["execution_authority"] as? String == "NONE" else {
        throw Refusal.message("invalid contract header")
    }
    return object
}

func requireSHA(_ object: [String: Any], _ fields: [String]) throws {
    let hex = CharacterSet(charactersIn: "0123456789abcdef")
    for field in fields {
        guard let value = object[field] as? String, value.utf8.count == 64,
              value.unicodeScalars.allSatisfy({ hex.contains($0) }) else {
            throw Refusal.message("invalid SHA-256 field")
        }
    }
}

func requireToken(_ object: [String: Any], _ field: String) throws {
    guard let value = object[field] as? String, !value.isEmpty, value.utf8.count <= 128 else {
        throw Refusal.message("invalid token field")
    }
    var previousWasSeparator = true
    for scalar in value.unicodeScalars {
        let ascii = scalar.value
        let alphanumeric = (65...90).contains(ascii) || (48...57).contains(ascii)
        let separator = ascii == 45 || ascii == 46 || ascii == 95
        if alphanumeric {
            previousWasSeparator = false
        } else if separator && !previousWasSeparator {
            previousWasSeparator = true
        } else {
            throw Refusal.message("invalid token field")
        }
    }
    if previousWasSeparator {
        throw Refusal.message("invalid token field")
    }
}

func requireTime(_ object: [String: Any], _ field: String) throws -> Date {
    guard let value = object[field] as? String else { throw Refusal.message("invalid timestamp") }
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime]
    guard !value.contains("."), value.hasSuffix("Z"), let date = formatter.date(from: value),
          formatter.string(from: date) == value else {
        throw Refusal.message("invalid canonical timestamp")
    }
    return date
}

func validateGenesis(_ data: Data) throws {
    let keys: Set<String> = ["schema_version", "domain_separator", "genesis_id", "installed_helper_sha256", "source_bundle_sha256", "activation_policy_sha256", "allowed_signers_sha256", "revocation_krl_sha256", "trust_snapshot_sha256", "initialized_at", "execution_authority"]
    let object = try strictObject(data, keys: keys, domain: "TIOS/INTAKE-AUTHORITY-GENESIS/v1")
    try requireToken(object, "genesis_id")
    try requireSHA(object, ["installed_helper_sha256", "source_bundle_sha256", "activation_policy_sha256", "allowed_signers_sha256", "revocation_krl_sha256", "trust_snapshot_sha256"])
    _ = try requireTime(object, "initialized_at")
}

func validateReceipt(_ data: Data) throws {
    let keys: Set<String> = ["schema_version", "domain_separator", "receipt_id", "authority_genesis_sha256", "monotonic_head_sha256", "activation_policy_sha256", "trust_snapshot_sha256", "status", "blockers", "issued_at", "expires_at", "execution_authority"]
    let object = try strictObject(data, keys: keys, domain: "TIOS/INTAKE-ACTIVATION-STATUS-RECEIPT/v1")
    try requireToken(object, "receipt_id")
    try requireSHA(object, ["authority_genesis_sha256", "monotonic_head_sha256", "activation_policy_sha256", "trust_snapshot_sha256"])
    guard let status = object["status"] as? String, let blockers = object["blockers"] as? [String],
          (status == "ACTIVE_NO_DECISIONS" && blockers.isEmpty) || (status == "BLOCKED" && !blockers.isEmpty) else {
        throw Refusal.message("invalid status/blocker combination")
    }
    for blocker in blockers {
        try requireToken(["blocker": blocker], "blocker")
    }
    if blockers != Array(Set(blockers)).sorted() { throw Refusal.message("blockers are not sorted and unique") }
    if try requireTime(object, "issued_at") >= requireTime(object, "expires_at") {
        throw Refusal.message("invalid receipt validity interval")
    }
}

func success(_ contract: String) throws {
    let blockers = ["EXTERNAL_ACTIVATION_NOT_EXECUTED", "SEMANTIC_BINDINGS_NOT_EXTERNALLY_VERIFIED", "TRUSTED_TIME_NOT_PERSISTED"]
    FileHandle.standardOutput.write(try canonicalJSON(["blockers": blockers, "contract": contract, "execution_authority": "NONE", "status": "CONTRACT_SYNTAX_VALID_PENDING_EXTERNAL_ACTIVATION"]))
    FileHandle.standardOutput.write(Data("\n".utf8))
}

do {
    let arguments = Array(CommandLine.arguments.dropFirst())
    if arguments == ["status", "--json"] {
        FileHandle.standardOutput.write(try canonicalJSON(["execution_authority": "NONE", "status": "SOURCE_ONLY_PENDING_EXTERNAL_ACTIVATION"]))
        FileHandle.standardOutput.write(Data("\n".utf8))
    } else if arguments == ["validate-authority-genesis"] {
        try validateGenesis(readBoundedInput()); try success("AUTHORITY_GENESIS")
    } else if arguments == ["validate-activation-receipt"] {
        try validateReceipt(readBoundedInput()); try success("ACTIVATION_STATUS_RECEIPT")
    } else {
        throw Refusal.message("usage: authority status --json | validate-authority-genesis | validate-activation-receipt")
    }
} catch { fail("authority validation refused: \(error)") }
