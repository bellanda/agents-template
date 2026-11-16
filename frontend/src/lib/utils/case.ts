// Utility for converting object keys between snake_case (Backend) and camelCase (Frontend)

export function camelToSnake(str: string): string {
  return str.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
}

export function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Converts all keys of an object to camelCase deeply.
 */
export function objectKeysToCamelCase(obj: unknown): unknown {
  if (Array.isArray(obj)) {
    return obj.map(objectKeysToCamelCase);
  }

  if (isObject(obj)) {
    const newObj: Record<string, unknown> = {};
    for (const key in obj) {
      if (Object.prototype.hasOwnProperty.call(obj, key)) {
        const camelKey = snakeToCamel(key);
        newObj[camelKey] = objectKeysToCamelCase(obj[key]);
      }
    }
    return newObj;
  }

  return obj;
}

/**
 * Converts all keys of an object to snake_case deeply.
 */
export function objectKeysToSnakeCase(obj: unknown): unknown {
  if (Array.isArray(obj)) {
    return obj.map(objectKeysToSnakeCase);
  }

  if (isObject(obj)) {
    const newObj: Record<string, unknown> = {};
    for (const key in obj) {
      if (Object.prototype.hasOwnProperty.call(obj, key)) {
        const snakeKey = camelToSnake(key);
        newObj[snakeKey] = objectKeysToSnakeCase(obj[key]);
      }
    }
    return newObj;
  }

  return obj;
}
