using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 地形の範囲情報
/// </summary>
[Serializable]
public class Bounds
{
    public float xMin;
    public float xMax;
    public float yMin;
    public float yMax;
    public float zMin;
    public float zMax;
}

/// <summary>
/// 地形データ
/// </summary>
[Serializable]
public class TerrainData
{
    public List<int> gridSize;
    public float resolution;
    public Bounds bounds;
    public List<List<float>> costMap;
    public List<float> start;
    public List<float> goal;
}

/// <summary>
/// 経路データ
/// </summary>
[Serializable]
public class PathData
{
    public List<List<float>> path;
    public float computationTime;
    public float pathLength;
    public int numWaypoints;
    public bool success;
    public string color;
}

/// <summary>
/// シナリオデータ（トップレベル）
/// </summary>
[Serializable]
public class ScenarioDataRaw
{
    public string scenarioId;
    public string scenarioName;
    public string complexity;
    public string mapSize;
    public TerrainData terrain;
    public List<PathEntry> paths; // JSONUtilityの制約で一度Listで受ける
}

/// <summary>
/// 経路エントリ（Dictionary変換用）
/// </summary>
[Serializable]
public class PathEntry
{
    public string key;
    public PathData value;
}

/// <summary>
/// 実際に使うシナリオデータ（Dictionary変換済み）
/// </summary>
public class ScenarioData
{
    public string scenarioId;
    public string scenarioName;
    public string complexity;
    public string mapSize;
    public TerrainData terrain;
    public Dictionary<string, PathData> paths;
}

/// <summary>
/// DataLoader: JSONからシナリオデータを読み込む
/// </summary>
public class DataLoader : MonoBehaviour
{
    /// <summary>
    /// Resources/PathData/{scenarioId}.json を読み込んで ScenarioData を返す
    /// </summary>
    public static ScenarioData LoadScenario(string scenarioId)
    {
        TextAsset jsonFile = Resources.Load<TextAsset>($"PathData/{scenarioId}");
        if (jsonFile == null)
        {
            Debug.LogError($"Failed to load: {scenarioId}.json");
            return null;
        }

        // JsonUtilityで一度生データとしてパース
        ScenarioDataRaw raw = null;
        try
        {
            raw = JsonUtility.FromJson<ScenarioDataRaw>(jsonFile.text);
        }
        catch (Exception e)
        {
            Debug.LogError($"JSON parse error: {e.Message}");
            return null;
        }

        if (raw == null)
        {
            Debug.LogError("Parsed scenario data is null");
            return null;
        }

        // Dictionary<string, PathData> に変換
        Dictionary<string, PathData> pathDict = new Dictionary<string, PathData>();
        if (raw.paths != null)
        {
            foreach (var entry in raw.paths)
            {
                if (entry != null && !string.IsNullOrEmpty(entry.key) && entry.value != null)
                {
                    pathDict[entry.key] = entry.value;
                }
            }
        }

        // ScenarioDataに詰め直す
        ScenarioData scenario = new ScenarioData
        {
            scenarioId = raw.scenarioId,
            scenarioName = raw.scenarioName,
            complexity = raw.complexity,
            mapSize = raw.mapSize,
            terrain = raw.terrain,
            paths = pathDict
        };

        Debug.Log($"Loaded scenario: {scenario.scenarioId}");
        if (scenario.terrain != null && scenario.terrain.gridSize != null)
            Debug.Log($"Terrain size: {scenario.terrain.gridSize[0]}x{scenario.terrain.gridSize[1]}");
        Debug.Log($"Paths loaded: {scenario.paths.Count}");

        return scenario;
    }
}
