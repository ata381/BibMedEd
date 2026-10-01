import { readFileSync } from "node:fs";
import { join } from "node:path";

export type ShapeType = "null" | "boolean" | "number" | "string" | "array" | "object";

export interface ShapeNode {
  type: ShapeType;
  nullable?: boolean;
  optional?: boolean;
  // null when the backend returned an empty list, so element shape is unknown.
  items?: ShapeNode | null;
  properties?: Record<string, ShapeNode>;
}

export const API_SHAPES_PATH = join(__dirname, "fixtures", "api-shapes.json");

export function loadApiShapes(): Record<string, ShapeNode> {
  return JSON.parse(readFileSync(API_SHAPES_PATH, "utf-8")) as Record<string, ShapeNode>;
}

function typeOf(value: unknown): ShapeType | "undefined" {
  if (value === null) return "null";
  if (Array.isArray(value)) return "array";
  const type = typeof value;
  if (type === "boolean" || type === "number" || type === "string" || type === "undefined") return type;
  if (type === "object") return "object";
  throw new Error(`Unsupported mock value of type ${type}`);
}

function describeShape(shape: ShapeNode): string {
  return shape.nullable ? `${shape.type} | null` : shape.type;
}

export function diffShape(shape: ShapeNode, value: unknown, path: string): string[] {
  const actual = typeOf(value);
  if (actual === "null") {
    return shape.type === "null" || shape.nullable ? [] : [`${path}: mock is null but backend returns ${describeShape(shape)}`];
  }
  if (actual !== shape.type) {
    return [`${path}: mock is ${actual} but backend returns ${describeShape(shape)}`];
  }
  if (shape.type === "array") {
    if (!shape.items) return [];
    const items = shape.items;
    return (value as unknown[]).flatMap((element, index) => diffShape(items, element, `${path}[${index}]`));
  }
  if (shape.type === "object") {
    return diffObject(shape.properties ?? {}, value as Record<string, unknown>, path);
  }
  return [];
}

function diffObject(properties: Record<string, ShapeNode>, value: Record<string, unknown>, path: string): string[] {
  const errors: string[] = [];
  for (const [key, property] of Object.entries(properties)) {
    if (!(key in value)) {
      if (!property.optional) errors.push(`${path}.${key}: missing from mock (backend returns ${describeShape(property)})`);
      continue;
    }
    errors.push(...diffShape(property, value[key], `${path}.${key}`));
  }
  for (const key of Object.keys(value)) {
    if (!(key in properties)) errors.push(`${path}.${key}: mock has a field the backend does not return`);
  }
  return errors;
}
