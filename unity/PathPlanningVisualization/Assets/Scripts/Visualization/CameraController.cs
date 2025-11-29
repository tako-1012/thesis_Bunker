using UnityEngine;

/// <summary>
/// インタラクティブカメラコントロール
/// マウス・キーボードで自由に視点変更
/// </summary>
public class CameraController : MonoBehaviour
{
    [Header("Movement Settings")]
    public float moveSpeed = 10f;
    public float fastMoveSpeed = 20f;
    public float rotationSpeed = 3f;
    public float zoomSpeed = 10f;
    
    [Header("Limits")]
    public float minHeight = 0.5f;
    public float maxHeight = 50f;
    
    [Header("Focus Settings")]
    public Transform focusTarget;
    public float focusDistance = 10f;
    
    private Vector3 lastMousePosition;
    private bool isDragging = false;
    
    void Update()
    {
        HandleMovement();
        HandleRotation();
        HandleZoom();
        HandleFocus();
    }
    
    void HandleMovement()
    {
        float speed = Input.GetKey(KeyCode.LeftShift) ? fastMoveSpeed : moveSpeed;
        
        Vector3 movement = Vector3.zero;
        
        if (Input.GetKey(KeyCode.W)) movement += transform.forward;
        if (Input.GetKey(KeyCode.S)) movement -= transform.forward;
        if (Input.GetKey(KeyCode.A)) movement -= transform.right;
        if (Input.GetKey(KeyCode.D)) movement += transform.right;
        if (Input.GetKey(KeyCode.Q)) movement += Vector3.down;
        if (Input.GetKey(KeyCode.E)) movement += Vector3.up;
        
        transform.position += movement * speed * Time.deltaTime;
        
        // 高さ制限
        Vector3 pos = transform.position;
        pos.y = Mathf.Clamp(pos.y, minHeight, maxHeight);
        transform.position = pos;
    }
    
    void HandleRotation()
    {
        if (Input.GetMouseButtonDown(1))
        {
            isDragging = true;
            lastMousePosition = Input.mousePosition;
        }
        
        if (Input.GetMouseButtonUp(1))
        {
            isDragging = false;
        }
        
        if (isDragging)
        {
            Vector3 delta = Input.mousePosition - lastMousePosition;
            
            transform.Rotate(Vector3.up, delta.x * rotationSpeed, Space.World);
            transform.Rotate(Vector3.right, -delta.y * rotationSpeed, Space.Self);
            
            lastMousePosition = Input.mousePosition;
        }
    }
    
    void HandleZoom()
    {
        float scroll = Input.GetAxis("Mouse ScrollWheel");
        if (Mathf.Abs(scroll) > 0.01f)
        {
            transform.position += transform.forward * scroll * zoomSpeed;
        }
    }
    
    void HandleFocus()
    {
        if (Input.GetKeyDown(KeyCode.F) && focusTarget != null)
        {
            FocusOnTarget(focusTarget.position);
        }
    }
    
    public void FocusOnTarget(Vector3 targetPosition)
    {
        Vector3 direction = (transform.position - targetPosition).normalized;
        transform.position = targetPosition + direction * focusDistance;
        transform.LookAt(targetPosition);
    }
    
    public void SetFocusTarget(Transform target)
    {
        focusTarget = target;
    }
}


