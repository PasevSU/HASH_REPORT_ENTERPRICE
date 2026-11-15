import assert from 'node:assert/strict';
const MAX_OBJECT_HEADER_SEPARATOR_BYTES=100, HEADER_SCAN_WORK_MULTIPLIER=8, MAX_SUPPORTED_OBJECT_NUMBER=2147483647;
function objectNumberError(message){return Error(message)}
function isPdfWhitespace2(byte) {
  return byte === 0 || byte === 9 || byte === 10 || byte === 12 || byte === 13 || byte === 32;
}
function isAsciiDigit(byte) {
  return byte !== void 0 && byte >= 48 && byte <= 57;
}
function readHeaderInteger(bytes, offset) {
  let next = offset;
  let value = 0;
  let isSafe = true;
  while (isAsciiDigit(bytes[next])) {
    const digit = (bytes[next] ?? 0) - 48;
    if (isSafe && value > Math.floor((MAX_SUPPORTED_OBJECT_NUMBER - digit) / 10)) {
      isSafe = false;
    } else if (isSafe) {
      value = value * 10 + digit;
    }
    next++;
  }
  return { value, next, isSafe };
}
function scanHeaderSeparators(bytes, offset, budget, allowEmpty = false) {
  let next = offset;
  let count = 0;
  let sawSeparator = false;
  let exceedsLimit = false;
  for (; ; ) {
    while (isPdfWhitespace2(bytes[next])) {
      consumeHeaderScanWork(budget);
      sawSeparator = true;
      count++;
      if (count > MAX_OBJECT_HEADER_SEPARATOR_BYTES) {
        // Reject this candidate immediately: never scan an unbounded whitespace run.
        return void 0;
      }
      next++;
    }
    if (bytes[next] !== 37) {
      return sawSeparator || allowEmpty ? { next, exceedsLimit } : void 0;
    }
    sawSeparator = true;
    while (next < bytes.length && bytes[next] !== 10 && bytes[next] !== 13) {
      consumeHeaderScanWork(budget);
      count++;
      if (count > MAX_OBJECT_HEADER_SEPARATOR_BYTES) {
        // Reject this candidate immediately: never scan an unbounded whitespace run.
        return void 0;
      }
      next++;
    }
  }
}
function consumeHeaderScanWork(budget) {
  if (budget.remaining === 0) {
    throw objectNumberError("Physical PDF object header compatibility scan work budget exhausted");
  }
  budget.remaining--;
}
function createHeaderScanBudget(byteLength) {
  const largestMultipliableLength = Math.floor(
    Number.MAX_SAFE_INTEGER / HEADER_SCAN_WORK_MULTIPLIER
  );
  return {
    remaining: byteLength > largestMultipliableLength ? Number.MAX_SAFE_INTEGER : byteLength * HEADER_SCAN_WORK_MULTIPLIER
  };
}
function isObjectKeyword(bytes, offset) {
  return bytes[offset] === 111 && bytes[offset + 1] === 98 && bytes[offset + 2] === 106;
}
function largestPhysicalHeaderObjectNumber(pdfBytes) {
  let largest = 0;
  const budget = createHeaderScanBudget(pdfBytes.length);
  for (let offset = 0; offset < pdfBytes.length; offset++) {
    if (!isAsciiDigit(pdfBytes[offset]) || isAsciiDigit(pdfBytes[offset - 1])) {
      continue;
    }
    const object = readHeaderInteger(pdfBytes, offset);
    const generationSeparator = scanHeaderSeparators(pdfBytes, object.next, budget);
    if (generationSeparator === void 0 || !isAsciiDigit(pdfBytes[generationSeparator.next])) {
      offset = object.next - 1;
      continue;
    }
    const generation = readHeaderInteger(pdfBytes, generationSeparator.next);
    const keywordSeparator = scanHeaderSeparators(pdfBytes, generation.next, budget, true);
    if (keywordSeparator === void 0 || !isObjectKeyword(pdfBytes, keywordSeparator.next)) {
      offset = object.next - 1;
      continue;
    }
    if (generationSeparator.exceedsLimit || keywordSeparator.exceedsLimit) {
      throw objectNumberError(
        "Physical PDF object header separator exceeds the compatibility scan limit"
      );
    }
    if (!object.isSafe || !generation.isSafe) {
      throw objectNumberError(
        "Physical PDF object header contains an unsupported object or generation number"
      );
    }
    largest = Math.max(largest, object.value);
    offset = keywordSeparator.next + 2;
  }
  return largest;
}

const good=new TextEncoder().encode('%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF');
assert.equal(largestPhysicalHeaderObjectNumber(good),1);
const adversarial=new TextEncoder().encode('%PDF-1.4\n'+('1 '+(' '.repeat(10000))+'x\n').repeat(120)+'2 0 obj\n<<>>\nendobj\n%%EOF');
assert.equal(largestPhysicalHeaderObjectNumber(adversarial),2);
console.log('PASS: normal object header and adversarial long separators, without budget exhaustion');
