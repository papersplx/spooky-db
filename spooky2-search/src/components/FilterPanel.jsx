import { useState, useRef, useEffect, useMemo } from 'react';
import './FilterPanel.css';

function computeFolderCounts(tree, collectionCounts) {
  function countNode(node) {
    if (!node.children || !node.children.length) {
      node.count = collectionCounts[node.fullPath] || 0;
    } else {
      node.count = 0;
      node.children.forEach(child => countNode(child));
      node.count += node.children.reduce((sum, c) => sum + (c.count || 0), 0);
    }
  }
  tree.forEach(node => countNode(node));
  return tree;
}

function filterTree(node, minCount) {
  if (node.children && node.children.length) {
    node.children = node.children
      .map(child => filterTree(child, minCount))
      .filter(child => child !== null);
    if (!node.children.length) {
      return null;
    }
    node.count = node.children.reduce((sum, c) => sum + (c.count || 0), 0);
  }
  if (node.count <= minCount) {
    return null;
  }
  return node;
}

function TreeLeaf({
  name,
  fullPath,
  selectedCollections,
  onToggleCollection,
  count,
}) {
  const isSelected = selectedCollections.includes(fullPath);

  return (
    <div className="tree-item tree-leaf">
      <span className="tree-dot" />
      <input
        type="checkbox"
        checked={isSelected}
        onChange={() => onToggleCollection(fullPath)}
      />
      <span className="tree-name" title={fullPath}>
        {name}
        <span className="tree-count"> ({count})</span>
      </span>
    </div>
  );
}

function TreeNode({
  name,
  children,
  selectedCollections,
  onToggleCollection,
  depth = 0,
}) {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = children.length > 0;

  const handleToggle = () => {
    setExpanded(!expanded);
  };

  const totalSelected = children.reduce((sum, child) => {
    if (child.children && child.children.length) {
      return sum + (child._selectedCount || 0);
    }
    return sum + (selectedCollections.includes(child.fullPath) ? 1 : 0);
  }, 0);
  const allSelected = totalSelected === children.length && children.length > 0;
  const someSelected = totalSelected > 0 && totalSelected < children.length;

  return (
    <div className="tree-node" style={{ paddingLeft: (depth * 1.2) + 'rem' }}>
      <div
        className="tree-item"
        onClick={handleToggle}
      >
        <span className="tree-toggle">
          {hasChildren ? (expanded ? '▼' : '▶') : (
            <span className="tree-dot" />
          )}
        </span>
        <input
          type="checkbox"
          checked={allSelected ? 'checked' : someSelected ? 'indeterminate' : false}
          onChange={() => {
            children.forEach(child => {
              if (child.children && child.children.length) {
                const descendants = getDescendantLeaves(child);
                descendants.forEach(desc => onToggleCollection(desc.fullPath));
              } else {
                onToggleCollection(child.fullPath);
              }
            });
          }}
        />
        <span className="tree-name" title={name}>
          {name}
          {hasChildren && <span className="tree-count"> ({children.reduce((s, c) => s + (c.count || 0), 0)})</span>}
        </span>
      </div>
      {expanded && hasChildren && (
        <div className="tree-children">
          {children.map(child => {
            if (child.children && child.children.length) {
              return (
                <TreeNode
                  key={child.fullPath}
                  name={child.name}
                  children={child.children}
                  selectedCollections={selectedCollections}
                  onToggleCollection={onToggleCollection}
                  depth={depth + 1}
                />
              );
            }
            return (
              <TreeLeaf
                key={child.fullPath}
                name={child.name}
                fullPath={child.fullPath}
                selectedCollections={selectedCollections}
                onToggleCollection={onToggleCollection}
                count={child.count || 0}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

function getDescendantLeaves(node, leaves) {
  if (!node.children || !node.children.length) {
    leaves.push(node.fullPath);
  } else {
    node.children.forEach(child => getDescendantLeaves(child, leaves));
  }
  return leaves;
}

function buildTree(collections) {
  const root = {};
  collections.forEach(coll => {
    const parts = coll.split('/');
    let current = root;
    parts.forEach((part, index) => {
      if (!current[part]) {
        current[part] = { name: part, children: {}, _fullPath: parts.slice(0, index + 1).join('/') };
      }
      current = current[part].children;
    });
  });

  function convert(node, parentPath) {
    var fullPath = parentPath ? parentPath + '/' + node.name : node.name;
    var children = Object.values(node.children || {}).map(function(child) {
      return convert(child, fullPath);
    });
    return { name: node.name, fullPath: fullPath, children: children };
  }

  return Object.values(root).map(function(node) {
    return convert(node, '');
  });
}

export default function FilterPanel({
   collections,
   collectionCounts,
   selectedCollections,
   onToggleCollection,
   modes,
   selectedModes,
   onToggleMode,
   categories,
   selectedCategories,
   onToggleCategory,
   onClearFilters,
 }) {
  const [expandedRoots, setExpandedRoots] = useState(new Set());
  const listRef = useRef(null);

  var tree = useMemo(function() {
    var rawTree = computeFolderCounts(buildTree(collections), collectionCounts);
    return rawTree
      .map(function(node) { return filterTree(node, 1); })
      .filter(function(node) { return node !== null; });
  }, [collections, collectionCounts]);

  var handleRootToggle = function(rootName) {
    setExpandedRoots(function(prev) {
      var next = new Set(prev);
      if (next.has(rootName)) {
        next.delete(rootName);
      } else {
        next.add(rootName);
      }
      return next;
    });
  };

  useEffect(function() {
    setExpandedRoots(new Set());
  }, [collections]);

  return (
    <div className="filter-panel">
      <h3>Filters</h3>

      <div className="filter-section">
        <div className="filter-header">
          <h4>Collections</h4>
          <button className="clear-link" onClick={onClearFilters}>
            Clear all
          </button>
        </div>
        <div className="filter-options tree" ref={listRef}>
          {tree.map(function(root) {
            return (
              <div key={root.name} className="tree-root">
                <div
                  className="tree-item"
                  onClick={function() { handleRootToggle(root.name); }}
                >
                  <span className="tree-toggle">
                    {expandedRoots.has(root.name) ? '▼' : '▶'}
                  </span>
                  <span className="tree-name" title={root.name}>
                    {root.name}
                    <span className="tree-count"> ({root.count})</span>
                  </span>
                </div>
                {expandedRoots.has(root.name) && (
                  <div className="tree-children">
                    <TreeNode
                      name={root.name}
                      children={root.children}
                      selectedCollections={selectedCollections}
                      onToggleCollection={onToggleCollection}
                      depth={0}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="filter-section">
        <h4>Mode</h4>
        <div className="filter-options">
          {modes.map(function(mode) {
            return (
              <label key={mode} className="checkbox-label">
                <input
                  type="checkbox"
                  checked={selectedModes.includes(mode)}
                  onChange={function() { onToggleMode(mode); }}
                />
                <span>{mode}</span>
              </label>
            );
          })}
        </div>
      </div>

      {categories && categories.length > 0 && (
        <div className="filter-section">
          <h4>Category</h4>
          <div className="filter-options">
            {categories.map(function(category) {
              return (
                <label key={category} className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={selectedCategories && selectedCategories.includes(category)}
                    onChange={function() { onToggleCategory && onToggleCategory(category); }}
                  />
                  <span>{category}</span>
                </label>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
